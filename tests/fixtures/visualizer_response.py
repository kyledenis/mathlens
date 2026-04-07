"""Fixtures for visualizer tests."""

SAMPLE_MANIM_SCENE = '''from manim import *

class HarmonicSeriesScene(Scene):
    def construct(self):
        title = Text("Harmonic Series Divergence", font_size=36)
        self.play(Write(title))
        self.wait(1)
        self.play(FadeOut(title))

        axes = Axes(x_range=[0, 20, 5], y_range=[0, 5, 1])
        self.play(Create(axes))
        self.wait(2)
'''
