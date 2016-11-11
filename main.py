"""`main` is the top level module for your Flask application."""
from pprint import pprint

# Import the Flask Framework
import flask
from flask import Flask
from flask import redirect
from flask import request
from google.appengine.api import users
from google.appengine.api import memcache

from util import login
from lever import LeverClient


app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

APP_NAME = 'Catapult'


lever_client = LeverClient()

def _extract_fields_as_keyval(fields, key):
    for field in fields:
        if field['text'] == key:
            return field['value']
    raise KeyError(key)

def _compile_feedback(candidate_id):
    feedbacks = lever_client.get_candidate_feedback(candidate_id)
    headers = []

    def completed_at_or_phone(feedback):
        if 'phone' in feedback['text'].lower():
            return 0
        return feedback['completedAt']

    feedbacks = sorted(
        feedbacks,
        key=completed_at_or_phone,
    )
    feedbacks = [feedback for feedback in feedbacks if feedback['completedAt'] is not None and feedback['text'] != "Intern Evaluations"]
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
            headers.append(dict(
                score=feedback['score'],
                interviewer=user['name'].strip(),
                interview_type=feedback['text'].strip(),
            ))
            feedback['feedback_text'] = feedback['fields'][0]['value']
            feedback['team_suggestion'] = _extract_fields_as_keyval(
                feedback['fields'],
                u'Team Suggestions',
            )

        except Exception as e:
            print e
            print 11111, 'failure!'
            pprint(feedback)
    return headers, feedbacks

def _determine_intern_fields(fields):
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
        cleaned_fields['other_random_fields'].append((
            clean_name,
            field['value'],
        ))
    return cleaned_fields

@app.route('/')
@login.login_required
def home():
    """Return a friendly HTTP greeting."""
    return flask.render_template(
        'home.html',
        title=APP_NAME,
    )


@app.route('/fetch_feedback', methods=['POST'])
@login.login_required
def fetch_feedback():
    """Return a friendly HTTP greeting."""
    candidate_id = request.form['candidate_id']
    return redirect(
        '/feedback/%s' % (candidate_id,),
    )

@app.route('/treb')
@login.login_required
def treb():
    return flask.render_template(
        'trebuchet.html',
        title=APP_NAME,
    )


@app.route('/fetch_internevals', methods=['POST'])
@login.login_required
def fetch_internevals():
    """Return a friendly HTTP greeting."""
    candidate_id = request.form['candidate_id']
    return redirect(
        '/trebuchet/%s' % (candidate_id,),
    )


def _more_than_four_months_old(timestamp):
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp/1000)
    return datetime.datetime.now() - datetime.timedelta(days=120) > dt


@app.route('/trebuchet/<candidate_id>')
@login.login_required
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
        if feedback['text'] != 'Intern Evaluations':
            continue
        if _more_than_four_months_old(feedback['completedAt']):
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
    )

@app.route('/me')
@login.login_required
def me():
    return flask.render_template(
        'me.html',
        title=APP_NAME,
        user=users.get_current_user(),
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
