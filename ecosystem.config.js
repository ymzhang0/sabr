module.exports = {
    apps: [
        {
            name: 'aiida-worker',
            cwd: '/Users/yimingzhang/Developer/aris-workspace/aiida-worker',
            script: 'uv',
            args: 'run --extra quantumespresso uvicorn main:app --host 127.0.0.1 --port 8001',
            interpreter: 'none',
            env: {
                PYTHONPATH: '.'
            }
        },
        {
            name: 'aris-api',
            cwd: '/Users/yimingzhang/Developer/aris-workspace/aris',
            script: '/Users/yimingzhang/Developer/aris-workspace/aris/.venv/bin/python',
            args: 'app_api.py',
            env: {
                PYTHONPATH: '/Users/yimingzhang/Developer/aris-workspace/aris'
            }
        },
        {
            name: 'aris-web',
            cwd: '/Users/yimingzhang/Developer/aris-workspace/aris/apps/web',
            script: 'npm',
            args: 'run dev -- --host 127.0.0.1 --port 5173',
        },
        {
            name: "aris-tunnel",
            script: "cloudflared",
            args: `tunnel run ${process.env.ARIS_TUNNEL_NAME || "aris-aiida-tunnel"}`,
            autorestart: true
        }
    ]
};
