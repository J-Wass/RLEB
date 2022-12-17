import global_settings
from global_settings import rleb_log_error

import time
from datetime import datetime


# Monitors health of other threads.
def health_check():
    """Every minute, check if all threads are still running and restart if needed."""
    time.sleep(global_settings.health_check_startup_latency)

    while True:
        # Monitor Threads
        if global_settings.thread_crashes["thread"] >= 5:
            global_settings.thread_health_check_enabled = False
            global_settings.health_enabled = False
            rleb_log_error("HEALTH: More than 5 thread crashes.")
            global_settings.queues["alerts"].put(
                "More than 5 thread crashes detected. Consider using `!restart`."
            )
        if global_settings.thread_crashes["asyncio"] >= 5:
            global_settings.thread_health_check_enabled = False
            global_settings.health_enabled = False
            rleb_log_error("HEALTH: More than 5 asyncio crashes.")
            global_settings.queues["alerts"].put(
                "More than 5 asyncio crashes detected. Consider using `!restart`."
            )

        # Monitor Asyncio Threads
        dead_asyncio_threads = []
        for (
            asyncio_thread,
            update_time,
        ) in global_settings.asyncio_threads_heartbeats.items():
            if not global_settings.asyncio_health_check_enabled:
                break

            # Can't check if an asyncio thread is alive, check heartbeat instead.
            if (
                datetime.now() - update_time
            ).total_seconds() > global_settings.asyncio_timeout:
                rleb_log_error(
                    "HEALTH: {0} asyncio thread has stopped responding! ({1} crashes)".format(
                        asyncio_thread, global_settings.thread_crashes["asyncio"]
                    )
                )
                global_settings.queues["alerts"].put(
                    (
                        "{0} asyncio thread has stopped responding! ({1} crashes)".format(
                            asyncio_thread, global_settings.thread_crashes["asyncio"]
                        ),
                        global_settings.BOT_COMMANDS_CHANNEL_ID,
                    )
                )
                dead_asyncio_threads.append(asyncio_thread)

        # Don't warn about this asyncio thread again.
        for dead_asyncio_thread in dead_asyncio_threads:
            del global_settings.asyncio_threads_heartbeats[dead_asyncio_thread]

        # Break before waiting for the interval.
        if not global_settings.health_enabled:
            break

        global_settings.threads_heartbeats["Health thread"] = datetime.now()

        time.sleep(30)
