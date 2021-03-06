import tensorflow as tf
from tensorflow.contrib.seq2seq import BasicDecoder, BasicDecoderOutput

class BasicContextDecoder(BasicDecoder):
    """Basic decoder with contextual information"""

    def __init__(self, cell, helper, initial_state, context=None, _output_layer=None):
        """Initialize BasicDecoder.
        Args:
            context: Tensor of size [batch_size, context_size]
                Context vector that will be concatenated with inputs
        """
        output_layer = None
        self._pseudo_output_layer = _output_layer
        super().__init__(cell, helper, initial_state, output_layer)
        self._context = context

    def step(self, time, inputs, state, name=None):
        with tf.name_scope(name, "BasicDecoderStep", (time, inputs, state)):
            if self._context is not None:
                inputs = tf.concat([inputs, self._context], axis=-1)

            _cell_outputs, cell_state = self._cell(inputs, state)
            if self._pseudo_output_layer is not None:
                cell_outputs = self._pseudo_output_layer(_cell_outputs)
            else: cell_outputs = _cell_outputs
            sample_ids = self._helper.sample(
                time=time, outputs=cell_outputs, state=cell_state)
            (finished, next_inputs, next_state) = self._helper.next_inputs(
                time=time,
                outputs=cell_outputs,
                state=cell_state,
                sample_ids=sample_ids)

        outputs = BasicDecoderOutput(_cell_outputs, sample_ids)
        return (outputs, next_state, next_inputs, finished)
