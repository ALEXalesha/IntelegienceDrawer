import torch
import torch.nn as nn

# EMNIST byclass: 10 digits + 26 uppercase + 26 lowercase = 62 classes.
CLASS_CHARS = (
    [str(d) for d in range(10)]
    + [chr(ord("A") + i) for i in range(26)]
    + [chr(ord("a") + i) for i in range(26)]
)
NUM_CLASSES = len(CLASS_CHARS)


class SketchNet(nn.Module):
    def __init__(self, num_classes=NUM_CLASSES):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),          # 28 -> 14
            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),          # 14 -> 7
            nn.Dropout(0.25),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 7 * 7, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        return self.head(self.features(x))
