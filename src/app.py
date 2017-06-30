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
# End Configuration

logger = logging.getLogger()
logger.setLevel(logging.INFO)
client = boto3.client('sdb')

def authenticate(token):
    if token not in SLACK_TOKENS:
        logger.error("Request token (%s) does not match expected.", token)
        raise Exception("Invalid request token")

def process_slash_request(params):
    token = params['token'][0]
    authenticate(token)

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
        current_game = client.get_attributes(DomainName='pokerbot_game', ItemName='meta')
        if 'Attributes' in current_game.keys():
            message_text = 'Whoops! A game is already in progress.\n'
            message_text += 'Use "/pokerbot reveal" to reveal votes & close the current game.\n'
            message_text += 'Use "/pokerbot reset" to delete all data and start fresh.'
            return Message(message_text).get_private_message()

        client.put_attributes(DomainName='pokerbot_game', ItemName='meta', Attributes=[
            { 'Name': 'team_id', 'Value': post_data['team_id'], 'Replace': True },
            { 'Name': 'channel_id', 'Value': post_data['channel_id'], 'Replace': True },
            { 'Name': 'response_url', 'Value': post_data['response_url'], 'Replace': True }
        ])

        message_text = '*A new round of planning poker has begun!*'
        if len(command_arguments) > 1:
            subject_arg = command_arguments[1]
            message_text += '\n*This round\'s subject: *' + str(subject_arg)

        message = Message(message_text)
        attachment = Attachment('Place your vote using the buttons below. <http://lab.gracehill.com/snippets/59|(details)>', None)
        attachment.add_action_button(AttachmentAction('vote', '1', '1', 'primary'))
        attachment.add_action_button(AttachmentAction('vote', '3', '3'))
        attachment.add_action_button(AttachmentAction('vote', '5', '5'))
        attachment.add_action_button(AttachmentAction('vote', '8', '8'))
        attachment.add_action_button(AttachmentAction('vote', '13', '13', 'danger'))
        message.add_attachment(attachment)
        return message.get_public_message()

    elif sub_command == 'tally':
        current_game = client.get_attributes(DomainName='pokerbot_game', ItemName='meta')
        if 'Attributes' not in current_game.keys():
            return Message("The poker planning game hasn't started yet.").get_private_message()

        vote_data = client.select(SelectExpression='select * from pokerbot_game where NOT itemName()="meta"')
        if 'Items' not in vote_data.keys():
            return Message('*No one has voted yet.*').get_public_message()

        names = [vote['Name'] for vote in vote_data['Items']]
        name_string = ""
        for name in sorted(names):
            name_string += '- ' + name + '\n'
        return Message('Votes so far:\n' + str(name_string)).get_public_message()

    elif sub_command == 'reveal':
        current_game = client.get_attributes(DomainName='pokerbot_game', ItemName='meta')
        if 'Attributes' not in current_game.keys():
            return Message("The poker planning game hasn't started yet.").get_private_message()

        vote_data = client.select(SelectExpression='select * from pokerbot_game where NOT itemName()="meta"')
        reset_game_data()

        if 'Items' not in vote_data.keys():
            return Message('*No one voted! Start a new round to try again.*').get_public_message()

        votes = {}
        for vote in vote_data['Items']:
            vote_value = vote['Attributes'][0]['Value']
            if not votes.has_key(vote_value):
                votes[vote_value] = []
            votes[vote_value].append(vote['Name'])

        # count votes and report on the results
        vote_set = set(votes.keys())
        vote_count = len(vote_set)
        if vote_count == 1:
            message = Message(':confetti_ball: *Wow!* :confetti_ball:')
            success_message = 'Everyone selected the same number: *' + str(vote_set.pop()) + '*'
            message.add_attachment(Attachment(success_message, 'good'))
            return message.get_public_message()
        else:
            message = Message(':thinking_face: *The votes are in!* The floor is open to discuss your choices.')
            for vote in votes:
                message.add_attachment(Attachment("*" + str(vote) + "* - " + str(", ".join(votes[vote])), 'warning'))
            return message.get_public_message()

    elif sub_command == 'reset':
        reset_game_data()
        message_text = "Data cleared by %s. Use '/pokerbot deal' to start a new round." % str(post_data['user_name'])
        return Message(message_text).get_public_message()

    elif sub_command == 'help':
        return Message('Pokerbot helps you play Agile/Scrum poker planning.\n\n' +
                              'Use the following commands:\n' +
                              ' `/pokerbot deal [subject]`: start the game, with an optional subject. \n' +
                              ' `/pokerbot tally`: show who\'s voted so far. \n' +
                              ' `/pokerbot reveal`: unveil the votes and open the floor!').get_private_message()
    else:
        return Message('Invalid command. Type */pokerbot help* for pokerbot commands.').get_private_message()

def process_interactive_request(params):
    params = json.loads(params['payload'][0])
    token = params['token']
    authenticate(token)

    post_data = {
        'team_id' : params['team']['id'],
        'team_domain' : params['team']['domain'],
        'channel_id' : params['channel']['id'],
        'channel_name' : params['channel']['name'],
        'user_id' : params['user']['id'],
        'user_name' : params['user']['name'],
        'vote_value' : params['actions'][0]['value'],
        'response_url' : params['response_url']
    }

    current_game = client.get_attributes(DomainName='pokerbot_game', ItemName='meta')
    if 'Attributes' not in current_game.keys():
        return Message("The poker planning game hasn't started yet.").get_private_message()

    vote_value = post_data['vote_value']
    user_name = post_data['user_name']

    vote_data = client.select(SelectExpression='select * from pokerbot_game where NOT itemName()="meta"')
    if vote_data.has_key('Items'):
        already_voted = user_name in [vote['Name'] for vote in vote_data['Items']]
    else:
        already_voted = False

    client.put_attributes(DomainName='pokerbot_game', ItemName=user_name, Attributes=[{
        'Name': 'vote',
        'Value': vote_value,
        'Replace': True
    }])

    if already_voted:
        return Message("You changed your vote to *%s*." % str(vote_value)).get_private_message()
    else:
        message = Message('%s voted' % (user_name))
        response_url = [pair for pair in current_game['Attributes'] if pair['Name'] == 'response_url'][0]['Value']
        send_delayed_message(response_url, message)
        return Message("You voted *%s*." % str(vote_value)).get_private_message()

def reset_game_data():
    active_data = client.select(SelectExpression='select * from pokerbot_game')
    client.batch_delete_attributes(DomainName='pokerbot_game', Items=active_data['Items'])

def lambda_handler(event, context):
    """Main Lambda handler
    The function that AWS Lambda is configured to run on POST request to the
    configuration path. This function handles the main functions of the Pokerbot
    including starting the game, voting, calculating and ending the game.
    """
    req_body = event['body']
    params = parse_qs(req_body)

    if params.has_key('token'):
        return process_slash_request(params)
    else:
        return process_interactive_request(params)

def send_delayed_message(url, message):
    """Send a delayed in_channel message.
    You can send up to 5 messages per user command.
    """
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    try:
        response = urllib2.urlopen(req, json.dumps(message.get_unwrapped_message()))
    except urllib2.URLError:
        logger.error("Could not send delayed message to %s", url)

class Attachment():
    def __init__(self, text, color=None):
        self.__attachment = {}
        self.__attachment['text'] = text
        self.__attachment['callback_id'] = 'pokerbot_attachments'
        self.__attachment['mrkdwn_in'] = ['text']
        if color != None:
            self.__attachment['color'] = color

    def add_action_button(self, action):
        if not self.__attachment.has_key('actions'):
            self.__attachment['actions'] = []
        self.__attachment['actions'].append(action.build())

    def build(self):
        return self.__attachment

class AttachmentAction():
    def __init__(self, name, text, value, style=None):
        self.__action = {}
        self.__action['name'] = name
        self.__action['text'] = text
        self.__action['value'] = value
        self.__action['type'] = 'button'
        if style != None:
            self.__action['style'] = style

    def build(self):
        return self.__action

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
        self.__message['replace_original'] = False

    def add_attachment(self, attachment):
        """Add attachment to Slack message.
        """
        if not self.__message.has_key('attachments'):
            self.__message['attachments'] = []

        self.__message['attachments'].append(attachment.build())

    def _wrap_message(self):
        """Formats the output.
        :returns: the message in an API Gateway-friendly format
        """
        self.wrapper = {}
        self.wrapper['statusCode'] = 200
        self.wrapper['headers'] = {}
        self.wrapper['body'] = str(self.__message)
        return self.wrapper

    def get_unwrapped_message(self):
        return self.__message

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
        self.__message['response_type'] = 'ephemeral'
        return self._wrap_message()
