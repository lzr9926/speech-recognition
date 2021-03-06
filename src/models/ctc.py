import os
from .base import BaseModel
import tensorflow as tf
from six.moves import xrange as range
from ..utils import ops_utils


class CTCModel(BaseModel):
    def __init__(self):
        super().__init__()

    def __call__(self, hparams, mode, batched_input, **kwargs):
        BaseModel.__call__(self, hparams, mode, batched_input, **kwargs)
        return self

    def get_ground_truth_label_placeholder(self): return [self.targets]
    def get_predicted_label_placeholder(self): return [self.dense_decoded]
    def get_ground_truth_label_len_placeholder(self): return [tf.no_op()]
    def get_predicted_label_len_placeholder(self): return [tf.no_op()]
    def get_decode_fns(self):
        return [
            lambda d: self._batched_input.decode(d, None)
        ]

    default_params = {
        "num_units": 640,
        "num_layers": 3,
        "decoder": "greedy",  # greedy or beam_search
    }

    def _assign_input(self):
        if self.eval_mode or self.train_mode:
            ((self.input_filenames, self.inputs, self.input_seq_len), (self.targets, self.target_seq_len)) = \
                self.iterator.get_next()
        else:
            self.input_filenames, self.inputs, self.input_seq_len = self.iterator.get_next()

    def _build_graph(self):
        with tf.variable_scope("ctc"):
            # generate a SparseTensor required by ctc_loss op.
            self.sparse_targets = ops_utils.sparse_tensor(self.targets, padding_value=self.hparams.vocab_size - 1)

            cells_fw = [tf.contrib.rnn.LSTMCell(self.hparams.num_units) 
                    for _ in range(self.hparams.num_layers)]
            cells_bw = [tf.contrib.rnn.LSTMCell(self.hparams.num_units) 
                    for _ in range(self.hparams.num_layers)]

            outputs, _, _ = tf.contrib.rnn.stack_bidirectional_dynamic_rnn(
                cells_fw, cells_bw, 
                self.inputs,
                sequence_length=self.input_seq_len,
                dtype=tf.float32
            )

            logits = tf.layers.dense(outputs, self.hparams.vocab_size)

            # Time major
            logits = tf.transpose(logits, (1, 0, 2))
            self.logits = logits

            loss = tf.nn.ctc_loss(self.sparse_targets, logits, self.input_seq_len)
            self.loss = tf.reduce_mean(loss)

            if self.hparams.decoder == "greedy":
                self.decoded, log_prob = tf.nn.ctc_greedy_decoder(logits, self.input_seq_len)
            elif self.hparams.decoder == "beam_search":
                self.decoded, log_prob = tf.nn.ctc_beam_search_decoder(logits, self.input_seq_len)
            
            self.dense_decoded = tf.sparse_tensor_to_dense(self.decoded[0], default_value=-1)

            # label error rate
            self.ler = tf.reduce_mean(tf.edit_distance(tf.cast(self.decoded[0], tf.int32),
                                                   self.sparse_targets))

        return self.loss

    def get_extra_ops(self):
        return []
