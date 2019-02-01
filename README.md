# Writing a systemd Service in Python

Many Linux distributions use [systemd] to manage the system's services (or *daemons*), for example to automatically start certain services in the correct order when the system boots.

Writing a systemd service in Python turns out to be easy, but the complexity of systemd can be daunting at first. This tutorial is intended to get you started.

When you feel lost or need the gritty details, head over to the [systemd documentation][systemd], which is pretty extensive. However, the docs are distributed over several pages, and finding what you're looking for isn't always easy. A good place to look up a particular systemd detail is [systemd.directives], which lists all the configuration options, command line parameters, etc., and links to their documentation.

Aside from this `README.md` file, this repository contains a basic implementation of a Python service consisting of a Python script (`python_demo_service.py`) and a systemd unit file (`python_demo_service.service`).

The systemd version we're going to work with is 229, so if you're using a different version (see `systemctl --version`) then check the systemd documentation for things that may differ.


## System and User Services

systemd supports both *system* and *user* services. System services run in the system's own systemd instance and provide functionalities for the whole system and all users. User services, on the other hand, run in a separate systemd instance tied to a specific user.

Even if your goal is to develop a system service it is a good idea to start with a user service, because it allows you to focus on getting the service up and running before dealing with the complexities of setting up a system service. Most of this tutorial targets user services, but there's [a section at the end](#creating-a-system-service) on how to go from a user service to a system service once you're ready.


## Creating a User Service

### Unit Files

To create a systemd service you need to create a corresponding *unit file*, which is a  plaint-text, ini-style configuration file. For this tutorial we will use a simple self-contained unit file, see [systemd.unit] for advanced approaches.

Unit files for user services can be put [in several places](https://www.freedesktop.org/software/systemd/man/systemd.unit.html#User%20Unit%20Search%20Path). Some of these require root access, but there are multiple possible places in your home directory. As far as I can tell, there is no established default choice for these, so for this tutorial we are going to use `~/.config/systemd/user/`.

Therefore, store the following unit description as `~/.config/systemd/user/python_demo_service.service`:

    [Unit]
    # Human readable name of the unit
    Description=Python Demo Service

Once you have done this, systemd will find our service:

    $ systemctl --user list-unit-files | grep python_demo_service
    python_demo_service.service         static

The unit options for systemd services are documented in [systemd.service].


### Connecting the Service to a Python Script

We can now start to write the actual Python code for the service. Let's start small with a script that simply prints a message every 5 seconds. Store the following script as `python_demo_service.py` in a directory of your choice:

    if __name__ == '__main__':
        import time

        while True:
            print('Hello from the Python Demo Service')
            time.sleep(5)

To link our service to our script, extend the unit file as follows:

    [Unit]
    Description=Python Demo Service

    [Service]
    # Command to execute when the service is started
    ExecStart=/usr/bin/python path/to/your/python_demo_service.py


### Manually Starting and Stopping the Service

Now our service can be started:

    $ systemctl --user start python_demo_service

Note that this command returns immediately. This is because systemd has created a separate process that runs our script. This means that we don't have to care about [the nasty details of correctly forking into a daemon process](https://www.python.org/dev/peps/pep-3143/#correct-daemon-behaviour) ourselves, since systemd does all the work for us. Yay!

We can check that our service is running:

    $ systemctl --user status python_demo_service
    ● python_demo_service.service - Python Demo Service
       Loaded: loaded (/home/torf/.config/systemd/user/python_demo_service.service; static; vendor preset: enabled)
       Active: active (running) since So 2018-12-30 17:46:03 CET; 2min 35s ago
     Main PID: 26218 (python)
       CGroup: /user.slice/user-1000.slice/user@1000.service/python_demo_service.service
               └─26218 /usr/bin/python /home/torf/projects/python-systemd-tutorial/python_demo_service.py

In the first line of the output we can see the `Description` from our unit file. The output also tells us the state of our service and the PID it is running as.

Obviously our service can also be stopped:

    $ systemctl --user stop python_demo_service
    $ systemctl --user status python_demo_service
    ● python_demo_service.service - Python Demo Service
       Loaded: loaded (/home/torf/.config/systemd/user/python_demo_service.service)
       Active: inactive (dead)


### STDOUT and STDERR

You might have noticed that the output of our script's `print` calls did not show up on your terminal. This is because systemd detached the service process from that terminal and also redirected the process's `STDOUT` and `STDERR` streams.

One thing to remember is that in Python, STDOUT and STDOUT are buffered. When running in a terminal, this means that output will only show up after a newline (`\n`) has been written. However, our service's STDOUT and STDERR are pipes, and in this case the buffer is only flushed once it is full. Hence the script's messages only turn up in systemd's logs after it has produced even more output.

To avoid this effect we need to disable the buffering of STDOUT and STDERR, and [one possibility to do so](https://stackoverflow.com/q/107705/857390) is to set the `PYTHONUNBUFFERED` environment variable. This can be done directly in our unit file by adding the following line to the `[Service]` section:

    Environment=PYTHONUNBUFFERED=1

As always when you change your unit file you need to tell systemd to reload its configuration, and (if your service is currently running), restart the service:

    $ systemctl --user daemon-reload
    $ systemctl --user restart python_demo_service

The output from our script should now show up in systemd's logs, which by default are redirected to syslog:

    $ grep 'Python Demo Service' /var/log/syslog
    Dec 30 18:05:34 leibniz python[26218]: Hello from the Python Demo Service

Another way to display your service's output is via

    $ journalctl --user-unit python_demo_service

There are many more possible configurations for logging. For example, you can redirect STDOUT and STDERR to files instead. See [systemd.exec] for details.


### Automatically Starting the Service during Boot

Many services are intended to be started automatically when the system boots. This is easy to achieve using systemd. First we need to attach our service to a suitable *target*: targets are special systemd units that are used for grouping other units and for synchronization during startup. See [systemd.target] for details about targets in general and [systemd.special] for a list of built-in targets.

For user services, the `default.target` is usually a good choice. Add the following to your unit file:

    [Install]
    WantedBy=default.target

Our service is now ready to be started automatically, but for that to actually happen we have to *enable* the service first:

    $ systemctl --user enable python_demo_service
    Created symlink from /home/torf/.config/systemd/user/default.target.wants/python_demo_service.service to /home/torf/.config/systemd/user/python_demo_service.service.

If you restart your system now then our service will be started automatically once you log in. After your last session is closed, your user's systemd instance (and with it, our service) will shutdown. You can make your user's systemd instance independant from your user's sessions (so that our service starts at boot time even if you don't log in and also keeps running until a shutdown/reboot) via

    $ sudo loginctl enable-linger $USER

To disable autostart, simply disable your service:

    $ systemctl --user disable python_demo_service
    Removed symlink /home/torf/.config/systemd/user/default.target.wants/python_demo_service.service.

Note that simply enabling a service does not start it, but only activates autostart during boot-up. Similarly, disabling a service doesn't stop it, but only deactivates autostart during boot-up. If you want to start/stop the service immediately then you still need to do that manually [as described above](#manually-starting-and-stopping-the-service) in addition to enabling/disabling the service.

To check whether your service is enabled, use

    $ systemctl --user list-unit-files | grep python_demo_service
    python_demo_service.service         enabled


### Automatically Restarting the Service after Failure

As with any other software, your service might crash. In that case, systemd can automatically try to restart it. By default, systemd will not do that, so you have to enable this functionality in your unit file.

systemd has several options to precisely configure under which circumstances your service should be restarted. A good starting point is to set `Restart=on-failure` in the `[Service]` section of your unit file:

    [Service]
    ...
    Restart=on-failure

This tells systemd to restart your daemon when it exits with a non-zero exit code. Other settings for `Restart` and related options are documented in [systemd.service]. As always you need to run `systemctl --user daemon-reload` for these changes to become effective.

We can simulate a crash by killing our service using the `SIGKILL` signal:

    $ systemctl --user --signal=SIGKILL kill python_demo_service

Afterwards, the logs will show that systemd restarted our service:

    $ journalctl --user-unit python_demo_service
    [...]
    Jan 31 12:55:24 leibniz python[3074]: Hello from the Python Demo Service
    Jan 31 12:55:29 leibniz python[3074]: Hello from the Python Demo Service
    Jan 31 12:55:32 leibniz systemd[1791]: python_demo_service.service: Main process exited, code=killed, status=9/KILL
    Jan 31 12:55:32 leibniz systemd[1791]: python_demo_service.service: Unit entered failed state.
    Jan 31 12:55:32 leibniz systemd[1791]: python_demo_service.service: Failed with result 'signal'.
    Jan 31 12:55:33 leibniz systemd[1791]: python_demo_service.service: Service hold-off time over, scheduling restart.
    Jan 31 12:55:33 leibniz systemd[1791]: Stopped Python Demo Service.
    Jan 31 12:55:33 leibniz systemd[1791]: Started Python Demo Service.
    Jan 31 12:55:33 leibniz python[3089]: Hello from the Python Demo Service
    Jan 31 12:55:38 leibniz python[3089]: Hello from the Python Demo Service
    [...]


### Notifying systemd when the Service is Ready

Often, a service needs to perform some initializiation before it is ready to perform its actual work. Your service can notify systemd once it has completed its initialization. This is particularly useful when other services depend on your service, since it allows systemd to delay starting these until your service is really ready.

The notification is done using the [sd_notify] system call. We'll use the [python-systemd] package to execute it, so [make sure it is installed](https://github.com/systemd/python-systemd#installation). Then add the following lines to our script:

    if __name__ == '__main__':
        import time
        import systemd.daemon

        print('Starting up ...')
        time.sleep(10)
        print('Startup complete')
        systemd.daemon.notify('READY=1')

        while True:
            print('Hello from the Python Demo Service')
            time.sleep(5)

You will also need to change the type of your service from `simple` (the default we've been previously using) to `notify`. Add the following line to the `[Service]` section of your unit file, and call `systemctl --user daemon-reload` afterwards.

    Type=notify

You can then see the notification in action by (re-)starting the service: `systemctl` will wait for the service's notification before returning.

    $ systemctl --user restart python_demo_service

You can do a lot more via [sd_notify], see its documentation for details.


## Creating a System Service

Once you have a working user service you can turn it into a system service. Remember, however, that system services run in the system's central systemd instance and have a greater potential for disturbing your system's stability or security when not implemented correctly. In many cases, this step isn't really necessary and a user service will do just fine.


### Stopping and Disabling the User Service

Before turning our service into a system service let's make sure that its stopped and disabled. Otherwise we might end up with both a user service and a system service.

    $ systemctl --user stop python_demo_service
    $ systemctl --user disable python_demo_service


### Moving the Unit File

Previously, we stored our unit file in a directory appropriate for user services (`~/.config/systemd/user/`). As with user unit files, systemd looks into [more than one directory](https://www.freedesktop.org/software/systemd/man/systemd.unit.html#System%20Unit%20Search%20Path) for system unit files. We'll be using `/etc/systemd/system/`', so move your unit file there and make sure that it has the right permissions

    $ sudo mv ~/.config/systemd/user/python_demo_service.service /etc/systemd/system/
    $ sudo chown root:root /etc/systemd/system/python_demo_service.service
    $ sudo chmod 644 /etc/systemd/system/python_demo_service.service

Our service is now a system service! This also means that instead of using `systemctl --user ...` we will now use `systemctl ...` (without the `--user` option) instead (or `sudo systemctl ...` if we're modifying something). For example:

    $ systemctl list-unit-files | grep python_demo_service
    python_demo_service.service                disabled

Similarly, use `journalctl --unit python_demo_service` to display the system service's logs.


### Moving the Python Script

Until now you have probably stored the service's Python script somewhere in your home directory. That was fine for a user service, but isn't optimal for a system service. A separate subdirectory in `/usr/local/lib` is a better choice:

    $ sudo mkdir /usr/local/lib/python_demo_service
    $ sudo mv ~/path/to/your/python_demo_service.py /usr/local/lib/python_demo_service/
    $ sudo chown root:root /usr/local/lib/python_demo_service/python_demo_service.py
    $ sudo chmod 644 /usr/local/lib/python_demo_service/python_demo-service.py

Obviously we also need to change the script's location in our unit file: update the `ExecStart=...` line to

    ExecStart=/usr/bin/python /usr/local/lib/python_demo_service/python_demo_service.py

and reload the changes via `sudo systemctl daemon-reload`.


### Using a Dedicated Service User

System services by default run as `root`, which is a security risk. Instead, we will use a user account dedicated to the service, so that we can use the usual security mechanisms (e.g. file permissions) to configure precisely what our service can and cannot access.

A good choice for the name of the service user is the name of the service. To create the user we will use the [useradd] command:

    $ sudo useradd -r -s /bin/false python_demo_service

Once you have created the user, add the following line to the `[Service]` section of your unit file:

    User=python_demo_service

After reloading the systemd configuration restarting our service, we can check that it runs as the correct user:

    $ sudo systemctl daemon-reload
    $ sudo systemctl restart python_demo_service
    $ sudo systemctl --property=MainPID show python_demo_service
    MainPID=18570
    $ ps -o uname= -p 18570
    python_demo_service


## Where to go from here

We now have a basic implementation of a system systemd service in Python. Depending on your goal, there are many ways to go forward. Here are some ideas:

* Add support for reloading the service's configuration without a hard restart. See the [`ExecReload`](https://www.freedesktop.org/software/systemd/man/systemd.service.html#ExecReload=) option.
* Explore the other features of the [python-systemd] package, for example the [`systemd.journal`](https://www.freedesktop.org/software/systemd/python-systemd/journal.html) module for advanced interaction with the systemd journal.

And of course, if you find an error in this tutorial or have an addition, feel free to create an issue or a pull request.

Happy coding!


[python-systemd]: https://github.com/systemd/python-systemd
[sd_notify]: https://www.freedesktop.org/software/systemd/man/sd_notify.html
[systemd]: https://www.freedesktop.org/wiki/Software/systemd/
[systemd.directives]: https://www.freedesktop.org/software/systemd/man/systemd.directives.html
[systemd.exec]: https://www.freedesktop.org/software/systemd/man/systemd.exec.html
[systemd.unit]: https://www.freedesktop.org/software/systemd/man/systemd.unit.html
[systemd.service]: https://www.freedesktop.org/software/systemd/man/systemd.service.html
[systemd.special]: https://www.freedesktop.org/software/systemd/man/systemd.special.html
[systemd.target]: https://www.freedesktop.org/software/systemd/man/systemd.target.html
[useradd]: https://linux.die.net/man/8/useradd

