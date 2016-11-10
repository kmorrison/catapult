"""`main` is the top level module for your Flask application."""
from pprint import pprint

# Import the Flask Framework
import flask
from flask import Flask
from flask import redirect
from flask import request
from google.appengine.api import users

from util import login
from lever import LeverClient


app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

APP_NAME = 'catapult'


lever_client = LeverClient()

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
        # TODO: We can probably cache this forever
        try:
            user = lever_client.get_user(feedback['user'])
            feedback['username'] = user['name']
            feedback['score'] = feedback['fields'][2]['value']
            feedback['feedback_texts'] = feedback['fields'][0]['value'].split('\n')
            feedback['team_recommendation'] = feedback['fields'][1]['value']

            headers.append(dict(
                score=feedback['fields'][2]['value'],
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
    candidate_id = request.form['candidate_id']
    return redirect(
        '/feedback/%s' % (candidate_id,),
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
