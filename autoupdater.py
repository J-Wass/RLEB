import time

import global_settings
from liqui import diesel
import data_bridge

def auto_update():
    while True:
        global_settings.auto_update_enabled.wait()  # Wait for there be autoupdates to check.
        global_settings.rleb_log_info("[AUTO UPDATER]: Starting auto update check.")
        
        auto_updates = global_settings.auto_updates.values()
        for auto_update in auto_updates:

            day_number = auto_update.day_number
            liquipedia_url =  auto_update.liquipedia_url
            
            options = auto_update.thread_options
            tourney_system= auto_update.thread_type
            stringified_options = "-".join(sorted(options.lower().split(",")))
            if stringified_options == "none":
                template = tourney_system
            else:
                template = f"{tourney_system}-{stringified_options}"

            fresh_markdown = diesel.get_make_thread_markdown(liquipedia_url, template, day_number)
            reddit_url = auto_update.reddit_url

            # https://www.reddit.com/r/RLCSnewsTest/comments/17oh7u8/auto_update_test/
            # becomes
            # 17oh7u8
            submission_id = reddit_url.split("/comments/")[1].split("/")[0]
            submission = global_settings.r.submission(id=submission_id)
            if not submission:
                global_settings.rleb_log_error(f"Could not find reddit url to autoupdating {reddit_url}")
                del global_settings.auto_updates[auto_update.auto_update_id]
                data_bridge.Data.singleton().delete_auto_update(auto_update)

            submission.edit(fresh_markdown)
            print(f"updating {reddit_url}")
        
        time.sleep(60)
