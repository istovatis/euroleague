"""Our own sound effects for the Reels that have sound (mvp.py, shotchart.py, race.py, roundmap.py, crowds.py, specialists.py): everything is synthesized here, so no
music or clips from elsewhere. Mix(total) is a mono track; put() places a sound at a time in seconds; write() limits,
normalizes and saves it as a WAV for render_reel.record()."""
import wave

import numpy as np

RATE = 44100


class Mix:
    def __init__(self, total, seed=7):
        self.total = total
        self.rng = np.random.default_rng(seed)
        self.mix = np.zeros(int((total + 1) * RATE))

    def put(self, sound, at, gain=1.0):
        i = int(at * RATE)
        sound = sound[:len(self.mix) - i]
        self.mix[i:i + len(sound)] += gain * sound

    @staticmethod
    def t(n):
        return np.arange(n) / RATE

    @staticmethod
    def lowpass(x, width):  # a moving average: crude, but enough for noise colour
        return np.convolve(x, np.ones(width) / width, mode="same")

    def decay(self, n, tau):
        return np.exp(-self.t(n) / tau)

    def tone(self, f0, f1, dur, tau):
        n = int(dur * RATE)
        return np.sin(2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / RATE) * self.decay(n, tau)

    def noise(self, dur):
        return self.rng.uniform(-1, 1, int(dur * RATE))

    def snare(self, gain):
        x = self.noise(.09)
        return gain * (x - self.lowpass(x, 12)) * self.decay(len(x), .025)

    def knock(self, gain):
        return gain * (self.tone(220, 140, .12, .03) + .4 * self.lowpass(self.noise(.12), 3) * self.decay(int(.12 * RATE), .01))

    def swoosh(self, at, gain=.18, dur=.3):
        w = self.noise(dur)
        self.put(gain * self.lowpass(w, 3) * np.sin(np.linspace(0, np.pi, len(w))), at)

    def chord(self, at, gain=.12):
        for f in (261.6, 329.6, 392.0, 523.3):
            self.put(gain * self.tone(f, f, 1.6, .6), at)

    def write(self, out):
        mix = np.tanh(1.4 * self.mix)  # a soft limiter
        mix = mix[:int(self.total * RATE)] / max(1e-9, np.abs(mix).max()) * .89
        with wave.open(str(out), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(RATE)
            f.writeframes((mix * 32767).astype("<i2").tobytes())
        return out
