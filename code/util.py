import subprocess
import sys
from time import sleep
import logging

logger = logging.getLogger(__name__)

def subprocess_cmd(command, attempt = 2):
    """
    Runs a bash command. Detect failure from the output stream.
    Retry the command a number of times before accepting failure
    :param command:
    :param attempt:
    :return:
    """
    logger.debug('Executing command: ' + command)
    process = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()
    stderr = stderr.strip()
    stdout = stdout.strip()

    if process.returncode != 0:
        if attempt != 0:
            logger.debug('Hit error ' + stderr + '. Trying again.')
            sleep(5)
            return subprocess_cmd(command, attempt - 1)
        elif attempt == 0:
            raise RuntimeError('Hit error while running command (' + command + ') \n' + stderr)
    return stdout


def str2bool(str):
    return str.lower() in ('yes', 'true', 't', '1')

