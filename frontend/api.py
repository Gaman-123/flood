import asyncio
from fastapi import FastAPI, WebSocket, BackgroundTasks, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
import subprocess
import os
import time

app = FastAPI(title="FloodRoute AI API")

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend statically
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'public')
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# Track connected clients for live websockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming commands if any
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Global status tracker
job_status = {
    "status": "idle", # idle, running, completed, error
    "progress": 0,
    "last_run": None
}

async def run_pipeline_task(payload: dict):
    global job_status
    job_status["status"] = "running"
    job_status["progress"] = 10
    
    await manager.broadcast(json.dumps({"type": "status", "data": job_status}))
    
    cwd = os.path.dirname(os.path.dirname(__file__)) # Project root
    
    try:
        # Build command based on payload config
        cmd = ["python", "main.py"]
        if getattr(payload, "amb_count", None):
             cmd.extend(["--amb_count", str(payload.get("amb_count", 2))])
             
        for i, coords in enumerate(payload.get("ambulances", [])):
            cmd.extend([f"--amb{i+1}", f"{coords['lat']},{coords['lon']},{coords['target_lat']},{coords['target_lon']}"])

        # Run process asynchronously avoiding blocking main thread
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Simulate progress updates while running
        for p in range(20, 95, 15):
             job_status["progress"] = p
             await manager.broadcast(json.dumps({"type": "status", "data": job_status}))
             await asyncio.sleep(2) # Give some padding
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            job_status["status"] = "completed"
            job_status["progress"] = 100
            job_status["last_run"] = time.time()
            
            # Send completion signal
            await manager.broadcast(json.dumps({
                "type": "status", 
                "data": job_status
            }))
            
            # Broadcast new stats if available
            stats_path = os.path.join(cwd, "live_stats.json")
            if os.path.exists(stats_path):
                with open(stats_path, 'r') as f:
                    stats = json.load(f)
                    await manager.broadcast(json.dumps({"type": "stats", "data": stats}))
        else:
            job_status["status"] = "error"
            print(f"Error executing pipeline: {stderr.decode()}")
            await manager.broadcast(json.dumps({"type": "error", "message": "Pipeline execution failed"}))
            
    except Exception as e:
         job_status["status"] = "error"
         await manager.broadcast(json.dumps({"type": "error", "message": str(e)}))

@app.post("/api/run")
async def trigger_pipeline(background_tasks: BackgroundTasks, payload: dict):
    if job_status["status"] == "running":
        return {"error": "A job is already running."}
    
    background_tasks.add_task(run_pipeline_task, payload)
    return {"message": "Pipeline triggered successfully"}

@app.get("/api/status")
async def get_status():
    return job_status

@app.get("/api/stats")
async def get_stats():
     stats_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "live_stats.json")
     if os.path.exists(stats_path):
         with open(stats_path, 'r') as f:
             return json.load(f)
     return {"error": "No stats available"}

@app.get("/")
def serve_dashboard():
    index_path = os.path.join(frontend_path, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend not built yet"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
