module.exports = {
    apps: [
        {
            name: 'aiida-worker',
            cwd: '/Users/yimingzhang/Developer/aiida-worker',
            script: 'uv',
            args: 'run --extra quantumespresso uvicorn main:app --host 127.0.0.1 --port 8001',
            interpreter: 'none',
            env: {
                PYTHONPATH: '.'
            }
        },
        {
            name: 'aris-api',
            cwd: '/Users/yimingzhang/Developer/aris',
            script: '/Users/yimingzhang/Developer/aris/.venv/bin/python',
            args: 'app_api.py',
            env: {
                PYTHONPATH: '/Users/yimingzhang/Developer/aris'
            }
        },
        {
            name: 'aris-web',
            cwd: '/Users/yimingzhang/Developer/aris/apps/web',
            script: 'npm',
            args: 'run dev',
        },
        {
            name: "aris-tunnel",
            script: "cloudflared",
            args: "tunnel run sabr-aiida-tunnel",
            autorestart: true
        }
    ]
};
