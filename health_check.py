import pathlib
import global_settings
from global_settings import rleb_log_error

import time
from datetime import datetime


# Monitors health of other threads.
def health_check():
    """Every minute, check if all threads are still running and restart if needed."""
    time.sleep(global_settings.health_check_startup_latency)

    while True:
        try:
            # Monitor Threads
            if global_settings.thread_crashes["thread"] >= 5:
                global_settings.thread_health_check_enabled = False
                global_settings.health_enabled = False
                rleb_log_error("HEALTH: More than 5 thread crashes.")
                global_settings.queues["alerts"].put(
                    (
                        "More than 5 thread crashes detected. Consider using `!restart`.",
                        global_settings.BOT_COMMANDS_CHANNEL_ID,
                    )
                )
            if global_settings.thread_crashes["asyncio"] >= 5:
                global_settings.thread_health_check_enabled = False
                global_settings.health_enabled = False
                rleb_log_error("HEALTH: More than 5 asyncio crashes.")
                global_settings.queues["alerts"].put(
                    (
                        "More than 5 asyncio crashes detected. Consider using `!restart`.",
                        global_settings.BOT_COMMANDS_CHANNEL_ID,
                    )
                )

            worst_heartbeat = 0

            # Monitor Asyncio Threads
            dead_asyncio_threads = []

            for (
                asyncio_thread,
                update_time,
            ) in global_settings.asyncio_threads_heartbeats.items():
                if not global_settings.asyncio_health_check_enabled:
                    break

                # Can't check if an asyncio thread is alive, check heartbeat instead.
                asyncio_heartbeat = (datetime.now() - update_time).total_seconds()

                worst_heartbeat = max(worst_heartbeat, round(asyncio_heartbeat))
                if asyncio_heartbeat > global_settings.asyncio_timeout:
                    rleb_log_error(
                        "HEALTH: {0} asyncio thread has stopped responding! ({1} crashes)".format(
                            asyncio_thread, global_settings.thread_crashes["asyncio"]
                        )
                    )
                    global_settings.queues["alerts"].put(
                        (
                            "{0} asyncio thread has stopped responding! ({1} crashes)".format(
                                asyncio_thread,
                                global_settings.thread_crashes["asyncio"],
                            ),
                            global_settings.BOT_COMMANDS_CHANNEL_ID,
                        )
                    )
                    dead_asyncio_threads.append(asyncio_thread)

            # Don't warn about this asyncio thread again.
            for dead_asyncio_thread in dead_asyncio_threads:
                del global_settings.asyncio_threads_heartbeats[dead_asyncio_thread]

            # Monitor dead threads.
            dead_threads = []
            for thread in global_settings.threads_to_check:
                thread_heartbeat = (
                    datetime.now() - global_settings.threads_heartbeats[thread]
                ).total_seconds()
                worst_heartbeat = max(worst_heartbeat, round(thread_heartbeat))
                if thread_heartbeat > global_settings.thread_timeout:
                    rleb_log_error(f"HEALTH: {thread} has stopped responding!")
                    global_settings.queues["alerts"].put(
                        (
                            f"{thread} has stopped responding!",
                            global_settings.BOT_COMMANDS_CHANNEL_ID,
                        )
                    )
                    dead_threads.append(thread)

            # Don't warn about this thread again.
            for dead_thread in dead_threads:
                global_settings.threads_to_check.remove(dead_thread)

            # Break before waiting for the interval.
            if not global_settings.health_enabled:
                break

            global_settings.threads_heartbeats["Health thread"] = datetime.now()

            current_path = str(pathlib.Path(__file__).parent.resolve())
            with open(f"{current_path}/heartbeat.txt", "w") as f:
                f.write(str(worst_heartbeat))

            time.sleep(30)
        except Exception as e:
            rleb_log_error(f"HEALTH: Hit exception when checking threads.\n{e}")
            global_settings.queues["alerts"].put(
                (
                    f"HEALTH: Hit exception when checking threads. {e}",
                    global_settings.BOT_COMMANDS_CHANNEL_ID,
                )
            )
            time.sleep(30)
