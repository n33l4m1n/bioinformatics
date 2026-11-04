# AI-native functional genomics

**Planned. Nothing is implemented yet.** Part of the [bioinformatics verticals](../README.md).

Pipelines that use learned sequence-to-function models to predict how DNA sequence and genetic variation affect
molecular function, and that check those predictions against measured data. Model predictions are treated as
evidence to be tested, never as results on their own; every run records the model, inputs and versions through
[biorun](../engine/README.md).
