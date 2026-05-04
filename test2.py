import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

t = np.linspace(0, 1, 1000, endpoint=True)
plt.plot(t, signal.square(2 * np.pi * 5 * t))

plt.xlabel("Time (Seconds)", fontname="Brush Script MT", fontsize=16)
plt.ylabel("Amplitude", fontname="Brush Script MT", fontsize=16)

plt.title("Square Wave", fontsize=18)
plt.show()
