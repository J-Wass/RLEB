import pathlib
import asyncio
import global_settings
from global_settings import rleb_log_error

from datetime import datetime


# Monitors health of asyncio tasks.
async def health_check(alert_channel):
    """Every 30 seconds, check if all asyncio tasks are healthy."""
    await asyncio.sleep(global_settings.health_check_startup_latency)

    while True:
        try:
            # Monitor crash counts
            if global_settings.thread_crashes["thread"] >= 5:
                global_settings.thread_health_check_enabled = False
                global_settings.health_enabled = False
                rleb_log_error("[HEALTH]: More than 5 thread crashes.")
                await alert_channel.send(
                    "More than 5 thread crashes detected. Consider using `!restart`."
                )
            if global_settings.thread_crashes["asyncio"] >= 5:
                global_settings.asyncio_health_check_enabled = False
                global_settings.health_enabled = False
                rleb_log_error("[HEALTH]: More than 5 asyncio crashes.")
                await alert_channel.send(
                    "More than 5 asyncio crashes detected. Consider using `!restart`."
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
                    await alert_channel.send(
                        "{0} asyncio thread has stopped responding! ({1} crashes)".format(
                            asyncio_thread,
                            global_settings.thread_crashes["asyncio"],
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
                    await alert_channel.send(f"{thread} has stopped responding!")
                    dead_threads.append(thread)

            # Don't warn about this thread again.
            for dead_thread in dead_threads:
                global_settings.threads_to_check.remove(dead_thread)

            # Break before waiting for the interval.
            if not global_settings.health_enabled:
                break

            global_settings.asyncio_threads_heartbeats["health"] = datetime.now()

            # Write heartbeat to file asynchronously
            current_path = str(pathlib.Path(__file__).parent.resolve())

            def write_heartbeat():
                with open(f"{current_path}/heartbeat.txt", "w") as f:
                    f.write(str(worst_heartbeat))

            await asyncio.to_thread(write_heartbeat)

            await asyncio.sleep(30)
        except Exception as e:
            rleb_log_error(f"HEALTH: Hit exception when checking asyncio tasks.\n{e}")
            try:
                await alert_channel.send(
                    f"HEALTH: Hit exception when checking asyncio tasks. {e}"
                )
            except:
                pass  # If we can't send alert, just log it
            await asyncio.sleep(30)
