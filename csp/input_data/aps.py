import random

import tensorflow as tf

from .base import BaseInputData
from ..utils import utils
from ..utils import wav_utils

DCT_COEFFICIENT_COUNT = 120

class BatchedInput(BaseInputData):
    num_features = DCT_COEFFICIENT_COUNT
    # num_classes = 3260 + 1
    # num_classes = 34331
    
    def __init__(self, hparams, mode):
        self.mode = mode
        self.hparams = hparams

        BaseInputData.__init__(self, hparams, mode)

        filenames, targets = [], []
        for line in open(self.data_filename, "r"):
            if self.mode != tf.estimator.ModeKeys.PREDICT:
                if line.strip() == "": continue
                filename, target = line.strip().split(' ', 1)
                targets.append(target)
            else:
                filename = line.strip()
            filenames.append(filename)
        self.size = len(filenames)
        self.input_filenames = filenames
        self.input_targets = targets

    def init_dataset(self):
        self.filenames = tf.placeholder(dtype=tf.string)
        self.targets = tf.placeholder(dtype=tf.string)

        src_dataset = tf.data.Dataset.from_tensor_slices(self.filenames)
        src_dataset = src_dataset.map(lambda filename: (filename, tf.py_func(self.load_input, [filename], tf.float32)))
        src_dataset = src_dataset.map(lambda filename, feat: (filename, feat, tf.shape(feat)[0]))

        if self.mode == tf.estimator.ModeKeys.PREDICT:
            src_tgt_dataset = src_dataset
        else:
            tgt_dataset = tf.data.Dataset.from_tensor_slices(self.targets)
            tgt_dataset = tgt_dataset.map(
                lambda str: tf.cast(tf.py_func(self.extract_target_features, [str], tf.int64), tf.int32))
            tgt_dataset = tgt_dataset.map(lambda feat: (tf.cast(feat, tf.int32), tf.shape(feat)[0]))

            src_tgt_dataset = tf.data.Dataset.zip((src_dataset, tgt_dataset))

        if self.mode == tf.estimator.ModeKeys.PREDICT:
            src_tgt_dataset.take(10)

        self.batched_dataset = utils.get_batched_dataset_bucket(
            src_tgt_dataset,
            self.hparams.batch_size,
            DCT_COEFFICIENT_COUNT,
            self.hparams.num_buckets,
            self.mode,
            padding_values=0 if self.hparams.input_unit == "char" else 1
        )

        self.iterator = self.batched_dataset.make_initializable_iterator()

    def init_from_wav_files(self, wav_filenames):
        src_dataset = tf.data.Dataset.from_tensor_slices(wav_filenames)
        src_dataset = wav_utils.wav_to_features(src_dataset, self.hparams, 40)
        src_dataset = src_dataset.map(lambda feat: (feat, tf.shape(feat)[0]))

        self.batched_dataset = utils.get_batched_dataset(
            src_dataset,
            self.hparams.batch_size,
            DCT_COEFFICIENT_COUNT,
            self.hparams.num_buckets, self.mode
        )

        self.iterator = self.batched_dataset.make_initializable_iterator()

    def extract_target_features(self, str):
        return [[int(x) for x in str.decode('utf-8').split(' ')]]

    def reset_iterator(self, sess, skip=0, shuffle=False, bucket_size=None):
        filenames = self.input_filenames
        targets = self.input_targets
        
        if shuffle:
            if bucket_size:
                shuffled_filenames = []
                shuffled_targets = []
                for i in range(0, len(filenames) // bucket_size):
                    start, end = i * bucket_size, min((i + 1) * bucket_size, len(filenames))
                    ls = list(zip(filenames[start:end], targets[start:end]))
                    random.shuffle(ls)
                    fs, ts = zip(*ls)
                    shuffled_filenames += fs
                    shuffled_targets += ts
                filenames = shuffled_filenames
                targets = shuffled_targets
            else:
                ls = list(zip(filenames, targets))
                random.shuffle(ls)
                filenames, targets = zip(*ls)

        filenames = filenames[skip:]
        targets = targets[skip:]

        sess.run(self.iterator.initializer, feed_dict={
            self.filenames: filenames,
            self.targets: targets
        })

    def decode(self, d):
        ret = []
        for c in d:
            if c <= 0: continue
            if self.hparams.input_unit == "word":
                if c == 1: return ret # sos
            # ret += str(c) + " "
            if self.decoder_map[c] == '<sos>': continue
            if self.hparams.input_unit == "word":
                val = self.decoder_map[c].split('+')[0]
            else:
                val = self.decoder_map[c]
            ret.append(val if c in self.decoder_map else '?')
        return ret