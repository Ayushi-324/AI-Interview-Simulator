#!/usr/bin/env python
import pprint
import logging
from collections import namedtuple

from requests.exceptions import ConnectionError
from client.exceptions import FaaspotException

from cli.arguments import parser, root_parsers
from commands.command import commands

# logging options
# https://docs.python.org/3/library/logging.html
# https://fangpenlin.com/posts/2012/08/26/good-logging-practice-in-python/
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(name)-8s] %(message)s',
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

external_loggers = ['requests', 'cloudify']
internal_loggers = ['fas', '__main__', 'commands', 'client', 'utils']


def set_logging_level(vrbose_level):
    internal_loggers_level = logging.INFO
    external_loggers_level = logging.WARNING

    if vrbose_level >= 1:
        internal_loggers_level = logging.DEBUG
    if vrbose_level >= 2:
        external_loggers_level = logging.INFO

    for logger_name in internal_loggers:
        logging.getLogger(logger_name).setLevel(internal_loggers_level)
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(external_loggers_level)


def main():
    args = parser.parse_args()
    input = dict(args._get_kwargs())

    selected_root_arg = [(root, input.get(root))
                         for root in root_parsers if input.get(root)][0]
    RootArg = namedtuple('RootArg', ['root', 'action'], verbose=False)
    root_arg = RootArg(*selected_root_arg)

    set_logging_level(args.verbose)

    del input[root_arg.root]
    del input['verbose']

    command = commands.get(root_arg.root)

    try:
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(command(root_arg.action, **input).run_function())
    except ConnectionError as ex:
        error_message = 'Failed to connect to FaaSpot server. \n' \
                        'Please verify connection parameters. \n' \
                        'Exception: {0}'.format(ex)
        print error_message
    except FaaspotException as ex:
        error_message = 'Failed to run command. \n' \
                        'Exception: {0}'.format(ex)
        print error_message
    except Exception as ex:
        print ex
        # error_message = 'Failed to run command. Exception: {0}'.format(ex)
        # print error_message


if __name__ == '__main__':
    main()
