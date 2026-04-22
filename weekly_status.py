from datetime import datetime

from tasks import Task, Event


def build_weekly_status(tasks: list[Task], scheduled_posts: list[Event]) -> str:
    """Builds the formatted !weekly status message comparing sheet tasks to scheduled Reddit posts.

    Returns a Discord-formatted string with one line per sheet task and an optional
    unrecognized section for Reddit threads not matched to any sheet task.
    """
    matched_post_ids: set[str] = set()
    lines: list[str] = []

    for task in tasks:
        is_manual = "Post" in task.event_schedule_time

        if is_manual:
            lines.append(f"📝 **{task.event_name}** (manual) | — | assigned: {task.event_creator}")
        else:
            try:
                time_string = task.event_schedule_time.replace("Schedule ", "")
                date_time_str = f"{task.event_date} {time_string} +0000"
                task_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M %z")
                timestamp = int(task_datetime.timestamp())
                matching = [p for p in scheduled_posts if int(p.event_seconds_since_epoch) == timestamp]
                if matching:
                    matched_post_ids.add(matching[0].id)  # type: ignore[arg-type]
                    lines.append(f"✅ **{task.event_name}** | <t:{timestamp}:F> | Prepared By: {task.event_creator}")
                else:
                    lines.append(f"❌ **{task.event_name}** | <t:{timestamp}:F> | Assigned To: {task.event_creator}")
            except Exception:
                lines.append(f"❓ **{task.event_name}** | (parse error)")

    unrecognized = [p for p in scheduled_posts if p.id not in matched_post_ids]

    output = "\n".join(lines) if lines else "No tasks found on the weekly sheet."

    if unrecognized:
        output += "\n\n**Unrecognized reddit threads:**"
        for p in unrecognized:
            ts = int(p.event_seconds_since_epoch)
            output += f"\n• {p.event_name} | <t:{ts}:F> | By: {p.event_creator}"

    return output
