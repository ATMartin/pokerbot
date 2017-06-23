# WIP: "Pokerbot"

## Purpose
PokerBot makes it easy to add a "Planning Poker" integration into your team's Slack organization.

## Installation
- Configure a custom slash command on your Slack org (You'll need admin permission for this)
- Create a new Lambda function on AWS
- Add an API Gateway trigger
- Add two environment variables:
  - SLACK_TOKEN: The token provided when configuring your slash command,
  - IMAGE_LOCATION: The root folder where your card & composite images are stored
- Point your slash command at your API Gateway endpoint
- Test that everything's working - run `/pokerbot help`
- Celebrate! You're about to make your Project Managers very, very happy...

## Configuration
- You can set up any scores you'd like in the VALID_SCORES dict - just add a number & an image path.
- Custom channels and the response avatar can be configured in Slack
- This app is configured to rely on open authentication on API Gateway. You can easily recode it to use a token or AWS auth parameters if you'd prefer.

## Use
Run `/pokerbot help` to see a list of commands.

## Screenshots
*Coming Soon!*

## TODO:
- [x] Fill in Readme
- [ ] Add generic card images
- [ ] Common command aliases ( `deal` => `start`, `reveal` => `close`, etc)
- [ ] Add support for non-numerics - `??`, `Infinity`, `Let's get a snack`?
- [ ] Setup/Install script?
- [ ] I18n messages for modularity
- [ ] GitLab / GitHub / Bitbucket support for linking issues
- [ ] Dynamic attachments? (click to vote, "yes/no" to restart empty reveal, etc
- [ ] Move all these TODOs to issues where they belong! :)
