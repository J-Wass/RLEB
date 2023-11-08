import time
import global_settings
from liqui import diesel

def auto_update():
    while True:
        global_settings.auto_update_enabled.wait()  # Wait for there be autoupdates to check.
        global_settings.rleb_log_info("[AUTO UPDATER]: Starting auto update check.")
        
        auto_updates = global_settings.auto_updates.values()
        breakpoint()
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
            print(f"updating {reddit_url} with \n\n{fresh_markdown}")
        
        time.sleep(60)
