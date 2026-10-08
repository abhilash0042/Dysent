import tensorflow as tf
print("TF", tf.__version__)
print("GPUs", tf.config.list_physical_devices("GPU"))
print("CUDA built", tf.test.is_built_with_cuda())
