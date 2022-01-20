from flask import Flask  
import rleb_settings   
from datetime import datetime                                                    

app = Flask(__name__)

@app.route("/")
def main():
    status = ['RLEB Status']

    # Asyncio
    asyncio_threads = ['--Discord Lightweight Threads (asyncio)--\n']
    now = datetime.now()
    for thread, response_datetime in rleb_settings.asyncio_threads.items():
        time_elapsed = round((now - response_datetime).total_seconds(), 1)
        asyncio_threads.append(f'Alive as of {time_elapsed}s ago - {thread} thread.')
    
    status.append('\n'.join(asyncio_threads))

    # Memory Log
    status.append('--In-Memory Log--')
    status.append('\n'.join(rleb_settings.memory_log))

    return '<pre>' + '\n\n'.join(status) + '</pre>'

def start():
    app.run()

if __name__ == "__main__":
    start()