module.exports = {
    apps: [
        {
            name: 'aiida-worker',
            cwd: '/Users/yimingzhang/Developer/aiida-worker',
            script: 'uv',
            args: 'run uvicorn main:app --host 127.0.0.1 --port 8001',
            interpreter: 'none',
            env: {
                PYTHONPATH: '.'
            }
        },
        {
            name: 'sabr-api',
            cwd: '/Users/yimingzhang/Developer/sabr',
            script: '/Users/yimingzhang/Developer/sabr/.venv/bin/python',
            args: 'app_api.py',
            env: {
                PYTHONPATH: '/Users/yimingzhang/Developer/sabr'
            }
        },
        {
            name: 'sabr-frontend',
            cwd: '/Users/yimingzhang/Developer/sabr/frontend',
            script: 'npm',
            args: 'run dev',
        }
    ]
};
