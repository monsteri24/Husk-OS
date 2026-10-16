"""Low-frequency /proc sampling. Missing GPU counters are reported as unknown."""
from pathlib import Path


class SystemSampler:
    def __init__(self):
        self.previous = None

    def sample(self):
        cpu = [int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
        total, idle = sum(cpu), cpu[3] + cpu[4]
        percent = 0.0
        if self.previous is not None:
            delta = total - self.previous[0]
            if delta > 0: percent = 100 * (1 - (idle - self.previous[1]) / delta)
        self.previous = total, idle
        mem = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, value = line.split(':', 1)
            mem[key] = int(value.split()[0]) * 1024
        gpu = None
        for path in Path('/sys/class/drm').glob('card*/device/gpu_busy_percent'):
            try:
                gpu = max(0, min(100, int(path.read_text()))); break
            except (OSError, ValueError):
                pass
        return dict(cpu_percent=max(0, min(100, percent)),
                    ram_total_bytes=mem['MemTotal'],
                    ram_used_bytes=max(0, mem['MemTotal'] - mem.get('MemAvailable', mem.get('MemFree', 0))),
                    gpu_percent=gpu)
