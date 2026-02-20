# engines/aiida/web/themes.py

THEMES = {
    'oxford': {
        '--sidebar-bg': '#002147',
        '--sidebar-text': '#ffffff',
        '--sidebar-sub': '#94a3b8',
        '--main-bg': '#f8f9fa',
        '--accent-color': '#1e40af',
        '--card-bg': '#ffffff',
        '--insight-bg': 'rgba(255, 255, 255, 0.05)',
        '--text-main': '#1e293b',
        '--border-color': '#e2e8f0'
    },
    'gemini_dark': {
        '--sidebar-bg': '#1e1f20',
        '--sidebar-text': '#e3e3e3',
        '--sidebar-sub': '#9aa0a6',
        '--main-bg': '#131314',
        '--accent-color': '#8ab4f8',
        '--accent-rgb': '138, 180, 248', # 呼吸动画需要
        '--card-bg': '#1e1f20',
        '--insight-bg': 'rgba(255, 255, 255, 0.04)',
        '--text-main': '#e3e3e3',        # 🚩 必须有这个
        '--border-color': '#444746'      # 🚩 必须有这个
    },
}