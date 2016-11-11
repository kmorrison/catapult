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
    feedbacks = [feedback for feedback in feedbacks if feedback['completedAt'] is not None]
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
            print 1111111, [field['text'] for field in feedback['fields']]
            feedback['score'] = _extract_fields_as_keyval(
                feedback['fields'],
                u'Rating',
            )
            feedback['feedback_texts'] = feedback['fields'][0]['value'].split('\n')
            feedback['team_suggestion'] = _extract_fields_as_keyval(
                feedback['fields'],
                u'Team Suggestions',
            )

            headers.append(dict(
                score=feedback['score'],
                interviewer=user['name'].strip(),
                interview_type=feedback['text'].strip(),
            ))
            pprint(feedback)
        except:
            print 11111, 'failure!'
            pprint(feedback)
    return headers, feedbacks



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
    print 1111111111
    candidate_id = request.form['candidate_id']
    return redirect(
        '/feedback/%s' % (candidate_id,),
    )


@app.route('/trebuchet/<candidate_id>')
@login.login_required
def intern_thing(candidate_id):
    """Return a friendly HTTP greeting."""
    feedbacks = lever_client.get_candidate_feedback(candidate_id)
    feedbacks = sorted(
        feedbacks,
        key=lambda x: x['completedAt'],
    )

    final_feedbacks = []
    for feedback in feedbacks:
        if feedback['text'] != 'Intern Evaluations':
            continue
        fake_feedback = {}
        for field in feedback['fields']:
            fake_feedback[field['text']] = field['value']
        final_feedbacks.append(fake_feedback)
    return flask.render_template(
        'trebuchet.html',
        content_stuff=final_feedbacks,
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
