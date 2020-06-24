# Python script for the Python Demo Service

if __name__ == '__main__':
    import time
    import systemd.daemon
    import signal
    import sys

    # graceful shutdown routine - gets called when process gets SIGTERM (systemd stop) or SIGINT (keyboard ctrl+c)
    def graceful_exit(signal_number,stack_frame):
       systemd.daemon.notify('STOPPING=1')
       print("Python Demo Service received signal {}. Stopping now.".format(signal.Signals(signal_number).name))
       time.sleep(5)
       print("Python Demo Service has shutdown. Bye bye now!")
       sys.exit(0)

    print('Starting up ...')

    # register SIGTERM and SIGINT handlers to enable graceful shutdown of service
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    time.sleep(10)
    print('Startup complete')
    # Tell systemd that our service is ready
    systemd.daemon.notify('READY=1')

    while True:
        print('Hello from the Python Demo Service')
        time.sleep(5)

