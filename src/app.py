"""
POKERBOT
Agile Scrum Pokerbot for Slack, hosted on AWS Lambda.

:Author: Alex Martin <martin.alex.t@gmail.com>
:Homepage: http://atmartin.io

Based on a script by Nate Yolles
:Source_Author: Nate Yolles <yolles@adobe.com>
:Source_Homepage: https://github.com/nateyolles/slack-pokerbot
"""

import os
import boto3
import logging
from urlparse import parse_qs
import json
import urllib2

# Start Configuration
SLACK_TOKENS = os.environ['SLACK_TOKEN']
IMAGE_LOCATION = os.environ['IMAGE_STORAGE']
COMPOSITE_IMAGE = IMAGE_LOCATION + 'composite.png'
VALID_VOTES = {
    0 : IMAGE_LOCATION + '0.png',
    1 : IMAGE_LOCATION + '1.png',
    2 : IMAGE_LOCATION + '2.png',
    3 : IMAGE_LOCATION + '3.png',
    5 : IMAGE_LOCATION + '5.png',
    8 : IMAGE_LOCATION + '8.png',
    13 : IMAGE_LOCATION + '13.png',
    20 : IMAGE_LOCATION + '20.png',
    40 : IMAGE_LOCATION + '40.png',
    100 : IMAGE_LOCATION + '100.png'
}
# End Configuration

logger = logging.getLogger()
logger.setLevel(logging.INFO)
poker_data = {}

def lambda_handler(event, context):
    """Main Lambda handler
    The function that AWS Lambda is configured to run on POST request to the
    configuration path. This function handles the main functions of the Pokerbot
    including starting the game, voting, calculating and ending the game.
    """
    req_body = event['body']
    params = parse_qs(req_body)

    token = params['token'][0]
    if token not in SLACK_TOKENS:
        logger.error("Request token (%s) does not match expected.", token)
        raise Exception("Invalid request token")

    post_data = {
        'team_id' : params['team_id'][0],
        'team_domain' : params['team_domain'][0],
        'channel_id' : params['channel_id'][0],
        'channel_name' : params['channel_name'][0],
        'user_id' : params['user_id'][0],
        'user_name' : params['user_name'][0],
        'command' : params['command'][0],
        'text' : params['text'][0] if 'text' in params.keys() else None,
        'response_url' : params['response_url'][0]
    }

    if (post_data['text'] == None) or (post_data['text'] == ''):
        return Message('Type */pokerbot help* for pokerbot commands.').get_private_message()

    command_arguments = post_data['text'].split(' ')
    sub_command = command_arguments[0]

    if sub_command == 'deal':
        if post_data['team_id'] not in poker_data.keys():
            poker_data[post_data['team_id']] = {}
        poker_data[post_data['team_id']][post_data['channel_id']] = {}

        message_text = '*A new round of planning poker has begun!*'
        if len(command_arguments) > 1:
            subject_arg = command_arguments[1]
            message_text += '\n*This round\'s subject: *' + str(subject_arg)

        message = Message(message_text)
        message.add_attachment('Vote by typing */pokerbot vote <number>*.', None, COMPOSITE_IMAGE)
        return message.get_public_message()

    elif sub_command == 'vote':
        if (post_data['team_id'] not in poker_data.keys() or
                post_data['channel_id'] not in poker_data[post_data['team_id']].keys()):
            return Message("The poker planning game hasn't started yet.").get_private_message()
        if len(command_arguments) < 2:
            return Message("Your vote was not counted. You didn't enter a number.").get_private_message()
        vote_sub_command = command_arguments[1]
        vote = None
        try:
            vote = int(vote_sub_command)
        except ValueError:
            return Message("Your vote was not counted. Please enter a number.").get_private_message()

        if vote not in VALID_VOTES:
            return Message("Your vote was not counted. Please enter a valid poker planning number.").get_private_message()

        already_voted = poker_data[post_data['team_id']][post_data['channel_id']].has_key(post_data['user_id'])
        poker_data[post_data['team_id']][post_data['channel_id']][post_data['user_id']] = {
            'vote' : vote,
            'name' : post_data['user_name']
        }

        if already_voted:
            return Message("You changed your vote to *%d*." % (vote)).get_private_message()
        else:
            message = Message('%s voted' % (post_data['user_name']))
            send_delayed_message(post_data['response_url'], message)
            return Message("You voted *%d*." % (vote)).get_private_message()

    elif sub_command == 'tally':
        if (post_data['team_id'] not in poker_data.keys() or
                post_data['channel_id'] not in poker_data[post_data['team_id']].keys()):

            return Message("The poker planning game hasn't started yet.").get_private_message()

        message = None
        names = []

        for player in poker_data[post_data['team_id']][post_data['channel_id']]:
            names.append(poker_data[post_data['team_id']][post_data['channel_id']][player]['name'])

        if len(names) == 0:
            message = Message('No one has voted yet.')
        else:
            name_string = ""
            for name in sorted(names):
                name_string += '- ' + name + '\n'
            message = Message('Votes so far:\n' + str(name_string))
        return message.get_public_message()

    elif sub_command == 'reveal':
        if (post_data['team_id'] not in poker_data.keys() or
                post_data['channel_id'] not in poker_data[post_data['team_id']].keys()):
            return Message("The poker planning game hasn't started yet.").get_private_message()

        votes = {}

        for player in poker_data[post_data['team_id']][post_data['channel_id']]:
            player_vote = poker_data[post_data['team_id']][post_data['channel_id']][player]['vote']
            player_name = poker_data[post_data['team_id']][post_data['channel_id']][player]['name']
            if not votes.has_key(player_vote):
                votes[player_vote] = []
            votes[player_vote].append(player_name)

        # reset the game by deleting the current channel's data
        del poker_data[post_data['team_id']][post_data['channel_id']]

        # count votes and report on the results
        vote_set = set(votes.keys())
        vote_count = len(vote_set)
        if vote_count == 0:
            return Message('*No one voted! Start a new round to try again.*').get_public_message()
        elif vote_count == 1:
            message = Message(':confetti_ball: *Wow!* :confetti_ball:')
            message.add_attachment('Everyone selected the same number.', 'good', VALID_VOTES.get(vote_set.pop()))
            return message.get_public_message()
        else:
            message = Message(':thinking_face: *The votes are in!* The floor is open to discuss your choices.')
            for vote in votes:
                message.add_attachment(str(", ".join(votes[vote])), 'warning', VALID_VOTES[vote], True)
            return message.get_public_message()

    elif sub_command == 'help':
        return Message('Pokerbot helps you play Agile/Scrum poker planning.\n\n' +
                              'Use the following commands:\n' +
                              ' `/pokerbot deal [subject]`: start the game, with an optional subject. \n' +
                              ' `/pokerbot vote`: cast your vote: ' + str(sorted(VALID_VOTES.keys())) + '\n' +
                              ' `/pokerbot tally`: show who\'s voted so far. \n' +
                              ' `/pokerbot reveal`: unveil the votes and open the floor!').get_private_message()
    else:
        return Message('Invalid command. Type */pokerbot help* for pokerbot commands.').get_private_message()

def send_delayed_message(url, message):
    """Send a delayed in_channel message.
    You can send up to 5 messages per user command.
    """
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    try:
        response = urllib2.urlopen(req, json.dumps(message.get_public_message()))
    except urllib2.URLError:
        logger.error("Could not send delayed message to %s", url)

class Message():
    """Public Slack message
    see 'Slack message formatting <https://api.slack.com/docs/formatting>'
    """
    def __init__(self, text):
        """Message constructor.
        :param text: text in the message
        :param color: color of the Slack message side bar
        """
        self.__message = {}
        self.__message['text'] = text

    def add_attachment(self, text, color=None, image=None, thumbnail=False):
        """Add attachment to Slack message.
        :param text: text in the attachment
        :param image: image in the attachment
        :param thumbnail: image will be thubmanail if True, full size if False
        """
        if not self.__message.has_key('attachments'):
            self.__message['attachments'] = []
        attachment = {}
        attachment['text'] = text
        if color != None:
            attachment['color'] = color
        if image != None:
            if thumbnail:
                attachment['thumb_url'] = image
            else:
                attachment['image_url'] = image
        self.__message['attachments'].append(attachment)

    def _wrap_message(self):
        """Formats the output.
        :returns: the message in an API Gateway-friendly format
        """
        self.wrapper = {}
        self.wrapper['statusCode'] = 200
        self.wrapper['headers'] = {}
        self.wrapper['body'] = str(self.__message)
        return self.wrapper

    def get_public_message(self):
        """Send a publicly-viewable message to Slack
        :returns: a formatted message payload for Slack
        """
        self.__message['response_type'] = 'in_channel'
        return self._wrap_message()

    def get_private_message(self):
        """Send an ephemeral ("your eyes only") message to Slack
        :returns: a formatted message payload for Slack
        """
        return self._wrap_message()
