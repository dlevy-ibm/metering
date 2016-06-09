from daemon import *
import optparse




def read_command_line():
    parser = optparse.OptionParser()


    parser.add_option('-l', '--log-file',
        help    = 'Optional. Path to log file. Default metering.log',
        dest    = 'log_file',
        metavar = 'LOG_FILE')

    parser.add_option('-d', '--log-level',
        help    = 'Optional. Turn debug level on in log file, True/False. Default False',
        dest    = 'log_level',
        metavar = 'LOG_LEVEL')

    parser.add_option('-c', '--cycle-time',
        help    = 'Optional Time in seconds for daemon to refresh it\'s data. Default 30 seconds',
        dest    = 'cycle_time',
        metavar = 'CYCLE_UPDATE_TIME')

    parser.add_option('-s', '--limit-synch-time',
        help    = 'Optional. Time in hours to synchronize the limit yaml file. Default 24 hours',
        dest    = 'limit_synch_time',
        metavar = 'LIMIT_SYNCH_TIME')



    (options, args) = parser.parse_args()
    log_level = options.log_level
    log_file = options.log_file
    cycle_time = options.cycle_time
    limit_synch_time = options.limit_synch_time
    if str2bool(log_level):
        log_level = "DEBUG"
    else:
        log_level = "INFO"
    if log_file is None:
        log_file = "metering.log"

    logging.basicConfig(filename=log_file, level=log_level, format='%(asctime)s %(levelname)s %(message)s')
    try:
        if cycle_time is not None:
            cycle_time = int(cycle_time)
        else:
            cycle_time = 30
        if limit_synch_time is not None:
            limit_synch_time = int(limit_synch_time)
        else:
            limit_synch_time = 24
    except ValueError:
        raise Exception("Cycle time or limit synch time should be an interger")

    return Daemon(cycle_time, limit_synch_time)



def main():
    try:
        daemon = read_command_line()
        daemon.start()
    except Exception as exception:
        logger.error(exception)
        raise exception


if __name__ == "__main__":
    main()