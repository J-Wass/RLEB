from datetime import datetime
import time
import prawcore

import global_settings
from liqui import diesel
import data_bridge


def auto_update():
    while True:
        global_settings.threads_heartbeats["Auto update thread"] = datetime.now()

        auto_updates = global_settings.auto_updates.values()
        if auto_updates:
            global_settings.rleb_log_info("[AUTO UPDATER]: Starting auto update check.")
        for auto_update in auto_updates:
            day_number = auto_update.day_number
            liquipedia_url = auto_update.liquipedia_url

            options = auto_update.thread_options
            tourney_system = auto_update.thread_type
            stringified_options = "-".join(sorted(options.lower().split(",")))
            if stringified_options == "none":
                template = tourney_system
            else:
                template = f"{tourney_system}-{stringified_options}"

            fresh_markdown = diesel.get_make_thread_markdown(
                liquipedia_url, template, day_number
            )

            # If markdown is the same as last time, don't write to reddit
            if liquipedia_url in global_settings.auto_update_markdown and global_settings.auto_update_markdown[liquipedia_url] == fresh_markdown:
                continue

            reddit_url = auto_update.reddit_url

            try:
                # https://www.reddit.com/r/RLCSnewsTest/comments/17oh7u8/auto_update_test/
                # becomes
                # 17oh7u8
                submission_id = reddit_url.split("/comments/")[1].split("/")[0]
                submission = global_settings.r.submission(id=submission_id)
                if not submission:
                    global_settings.rleb_log_error(
                        f"Could not find reddit url to auto update {reddit_url}"
                    )
                    # todo uncomment this once the discord thread is consuming from it.
                    #global_settings.queues["auto_update"].append(f"Could not find reddit url to auto update {reddit_url}")
                    del global_settings.auto_updates[auto_update.auto_update_id]
                    data_bridge.Data.singleton().delete_auto_update(auto_update)

                if submission.selftext == fresh_markdown:
                    continue

                global_settings.rleb_log_info(f"[AUTO UPDATER]: Updating {auto_update.reddit_url}")
                
                submission.edit(fresh_markdown)
                global_settings.auto_update_markdown[liquipedia_url] = fresh_markdown
            except AssertionError as e:
                if "429" in str(e):
                    time.sleep(60 * 11)
                    global_settings.rleb_log_error(f"[AUTO UPDATER]: {str(e)}")
            except prawcore.exceptions.ServerError as e:
                pass  # Reddit server borked, wait an interval and try again
            except prawcore.exceptions.RequestException as e:
                time.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                global_settings.rleb_log_error(f"[AUTO UPDATER]: Failed to auto update reddit thread {auto_update.reddit_url}. {str(e)}")

        time.sleep(60)
