"""`main` is the top level module for your Flask application."""
from pprint import pprint

# Import the Flask Framework
import flask
from flask import Flask
from flask import redirect
from flask import request
from google.appengine.api import memcache

from util import login
from lever import LeverClient


app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

APP_NAME = 'Catapult'
TEAM_FEEDBACK_KEY = u"Did the candidate give you any information about their interests that would help determine team fit?"
ANYTHING_ELSE_TO_KNOW_KEY = u"Is there anything else we should consider when making the final hiring decision?"


lever_client = LeverClient()

def _extract_fields_as_keyval(fields, key, allow_missing=False):
    for field in fields:
        if field['text'] == key:
            return field['value']
    if allow_missing:
        return ''
    raise KeyError(key)

def _truncate_header(header):
    # Strip out the word "Engineering" because it's redundant
    if header['interview_type'].startswith('Engineering - '):
        header['interview_type'] = header['interview_type'][len('Engineering - '):]
    try:
        score = int(header['score'][0])
        header['score'] = str(score)
    except Exception:
        pass
    return header

class InterviewTypes(object):
    PROBLEM_SOLVING = 'problem solving'
    SYSTEM_DESIGN = 'system design'
    PLAYS_WELL = 'plays well with others'
    OWNERSHIP = 'ownership'


FEEDBACK_ORDERING = [
    InterviewTypes.PROBLEM_SOLVING,
    InterviewTypes.SYSTEM_DESIGN,
    InterviewTypes.PLAYS_WELL,
    InterviewTypes.OWNERSHIP,
]


def _assign_arbitrary_feedback_ordering(feedback):
    feedback_title = feedback['text'].lower()
    for rank, interview_type in enumerate(FEEDBACK_ORDERING):
        if interview_type in feedback_title:
            # Increment by 1 since 0 is reserved for phone interviews, which
            # must come first :P
            return rank + 1
    return None


def _compile_feedback(candidate_id):
    feedbacks = lever_client.get_candidate_feedback(candidate_id)
    headers = []

    def arbitrary_order_to_be_consistent_with_docs(feedback):
        # Regardless of if it's an arbitrary order or not, phone interviews
        # always go first.
        if 'phone' in feedback['text'].lower():
            return 0
        if _assign_arbitrary_feedback_ordering(feedback) is not None:
            return _assign_arbitrary_feedback_ordering(feedback)
        return feedback['completedAt']

    feedbacks = sorted(
        feedbacks,
        key=arbitrary_order_to_be_consistent_with_docs,
    )
    feedbacks = [feedback for feedback in feedbacks if feedback['completedAt'] is not None and not feedback['text'].startswith("Intern Evaluations")]
    for feedback in feedbacks:
        try:
            # TODO: We can probably cache this forever
            user = memcache.get(feedback['user'])
            if user is None:
                user = lever_client.get_user(feedback['user'])
                memcache.add(
                    feedback['user'],
                    user,
                    60 * 60 * 24 * 7,
                )

            feedback['username'] = user['name']
            feedback['score'] = _extract_fields_as_keyval(
                feedback['fields'],
                u'Rating',
            )
            header = dict(
                score=feedback['score'],
                interviewer=user['name'].strip(),
                interview_type=feedback['text'].strip(),
            )
            headers.append(_truncate_header(header))

            feedback['feedback_text'] = feedback['fields'][0]['value']


            # There are two types of team feedback, the old "Team Suggestion"
            # and the newer, really long one defined by TEAM_FEEDBACK_KEY.
            # Account for both of these and conditionally include them in the
            # feedback payload
            feedback['team_suggestion'] = _extract_fields_as_keyval(
                feedback['fields'],
                u'Team Suggestions',
                allow_missing=True,
            )
            feedback['team_feedback'] = _extract_fields_as_keyval(
                feedback['fields'],
                TEAM_FEEDBACK_KEY,
                allow_missing=True,
            )
            feedback['anything_else_we_should_know'] = _extract_fields_as_keyval(
                feedback['fields'],
                ANYTHING_ELSE_TO_KNOW_KEY,
                allow_missing=True,
            )

        except Exception as e:
            print e
            print 11111, 'failure!'
            pprint(feedback)
    return headers, feedbacks

def _is_intern_form_v2(fields):
    # New form was released that allowed the reviewer to provide notes for each
    # evaluation metric, whereas before there was one overall notes field.
    # Figure out which one we're presenting for.
    notes_field_count = 0
    for field in fields:
        if field['text'].lower().startswith('notes'):
            notes_field_count += 1
        if notes_field_count > 1:
            return True
    return False

def _determine_intern_fields_form_v1(fields):
    cleaned_fields = dict(
        overall_score=None,
        notes=None,
        other_random_fields=[],
    )
    for field in fields:
        if field['text'].lower().startswith('overall'):
            cleaned_fields['overall_score'] = field['value']
            continue
        if field['text'].lower().startswith('notes'):
            cleaned_fields['notes'] = field['value']
            continue
        clean_name = field['text'].split('-')[0].strip()
        cleaned_fields['other_random_fields'].append(dict(
            label=clean_name,
            text=field['value'],
        ))
    return cleaned_fields

def _determine_intern_fields_form_v2(fields):
    cleaned_fields = dict(
        overall_score=None,
        notes=None,
        other_random_fields=[],
    )
    current_eval_field = {}
    for field in fields:
        if field['text'].lower().startswith('overall'):
            cleaned_fields['overall_score'] = field['value']
            continue
        if field['text'].lower().startswith('notes'):
            # Notes field corresponds to previous eval field in v2. Append to
            # fields list then clear the slate.
            current_eval_field['notes'] = field['value']
            cleaned_fields['other_random_fields'].append(current_eval_field)
            current_eval_field = {}
            continue
        clean_name = field['text'].split('-')[0].strip()
        if current_eval_field:
            # Have a current eval being considering means there was no notes,
            # so we can persist the current as is and assume this iteration is
            # starting a next one.
            cleaned_fields['other_random_fields'].append(current_eval_field)
            current_eval_field = {}
        current_eval_field = dict(
            label=clean_name,
            text=field['value'],
        )
    if current_eval_field:
        cleaned_fields['other_random_fields'].append(current_eval_field)
    return cleaned_fields

def _determine_intern_fields(fields):
    if _is_intern_form_v2(fields):
        return _determine_intern_fields_form_v2(fields)
    else:
        return _determine_intern_fields_form_v1(fields)


@app.route('/')
@login.admin_required
@login.company_login_required
@login.login_required
def home():
    """Return a friendly HTTP greeting."""
    return flask.render_template(
        'home.html',
        title=APP_NAME,
    )


@app.route('/fetch_feedback', methods=['POST'])
@login.login_required
@login.company_login_required
@login.admin_required
def fetch_feedback():
    """Return a friendly HTTP greeting."""
    candidate_id = request.form['candidate_id']
    return redirect(
        '/feedback/%s' % (candidate_id,),
    )

@app.route('/treb')
@login.login_required
@login.company_login_required
@login.admin_required
def treb():
    return flask.render_template(
        'trebuchet.html',
        title=APP_NAME,
    )


@app.route('/fetch_internevals', methods=['POST'])
@login.login_required
@login.company_login_required
@login.admin_required
def fetch_internevals():
    """Return a friendly HTTP greeting."""
    candidate_id = request.form['candidate_id']
    return redirect(
        '/trebuchet/%s' % (candidate_id,),
    )


def _more_than_n_months_old(timestamp, n=7):
    # https://jira.yelpcorp.com/browse/ENGREC-259, change lookback period to 7 months
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp/1000)
    return datetime.datetime.now() - datetime.timedelta(days=n * 30) > dt


@app.route('/trebuchet/<candidate_id>')
@login.login_required
@login.company_login_required
@login.admin_required
def intern_thing(candidate_id):
    """Return a friendly HTTP greeting."""
    feedbacks = lever_client.get_candidate_feedback(candidate_id)
    feedbacks = [feedback for feedback in feedbacks if feedback['completedAt'] is not None]
    feedbacks = sorted(
        feedbacks,
        key=lambda x: x['completedAt'],
    )

    headers = []
    final_feedbacks = []
    for feedback in feedbacks:
        if not feedback['text'].startswith('Intern Evaluations'):
            continue
        if _more_than_n_months_old(feedback['completedAt'], n=7):
            continue
        user = memcache.get(feedback['user'])
        if user is None:
            user = lever_client.get_user(feedback['user'])
            memcache.add(
                feedback['user'],
                user,
                60 * 60 * 24 * 7,
            )

        cleaned_fields = _determine_intern_fields(feedback['fields'])
        cleaned_fields['username'] = user['name']
        final_feedbacks.append(cleaned_fields)
        headers.append(dict(
            score=cleaned_fields['overall_score'],
            interviewer=user['name'].strip(),
        ))
    return flask.render_template(
        'trebuchet.html',
        feedbacks=final_feedbacks,
        candidate=lever_client.get_candidate(candidate_id),
        headers=headers,
    )

@app.route('/feedback/<candidate_id>')
@login.login_required
@login.company_login_required
@login.admin_required
def feedback(candidate_id):
    headers, feedbacks = _compile_feedback(candidate_id)
    candidate = lever_client.get_candidate(candidate_id)
    return flask.render_template(
        'home.html',
        title=APP_NAME,
        candidate_id=candidate_id,
        candidate=candidate,
        headers=headers,
        feedbacks=feedbacks,
        team_feedback_key=TEAM_FEEDBACK_KEY,
        anything_to_know_key=ANYTHING_ELSE_TO_KNOW_KEY,
    )

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def page_error(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500

app.secret_key = 'Change me.'
