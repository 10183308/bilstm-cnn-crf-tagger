from __future__ import print_function

import random
import time

from sequences_indexer import SequencesIndexer
from datasets_bank import DatasetsBank
from evaluator import Evaluator
from models.tagger_birnn import TaggerBiRNN
from utils import *

print('Hello, train/dev/test script!')

emb_fn = 'embeddings/glove.6B.100d.txt'
gpu = 0 # "-1" means for CPU

caseless = True
shrink_to_train = False
unk = None
delimiter = ' '
epoch_num = 3

rnn_hidden_size = 101
dropout_ratio = 0.5
clip_grad = 5.0
opt_method = 'sgd'

lr = 0.015
momentum = 0.9
batch_size = 5

debug_mode = False
verbose = True

seed_num = 42
np.random.seed(seed_num)
torch.manual_seed(seed_num)

freeze_embeddings = False

if gpu >= 0:
    torch.cuda.set_device(gpu)
    torch.cuda.manual_seed(seed_num)

# Select data
if (1 == 1):
    # Essays
    fn_train = 'data/argument_mining/persuasive_essays/es_paragraph_level_train.txt'
    fn_dev = 'data/argument_mining/persuasive_essays/es_paragraph_level_dev.txt'
    fn_test = 'data/argument_mining/persuasive_essays/es_paragraph_level_test.txt'
else:
    # CoNNL-2003 NER shared task
    fn_train = 'data/NER/CoNNL_2003_shared_task/train.txt'
    fn_dev = 'data/NER/CoNNL_2003_shared_task/dev.txt'
    fn_test = 'data/NER/CoNNL_2003_shared_task/test.txt'

# Load CoNNL data as sequences of strings of tokens and corresponding tags
token_sequences_train, tag_sequences_train = read_CoNNL(fn_train)
token_sequences_dev, tag_sequences_dev = read_CoNNL(fn_dev)
token_sequences_test, tag_sequences_test = read_CoNNL(fn_test)

# SequenceIndexer is a class to convert tokens and tags as strings to integer indices and back
sequences_indexer = SequencesIndexer(caseless=caseless, verbose=verbose, gpu=gpu)
sequences_indexer.load_embeddings(emb_fn=emb_fn, delimiter=delimiter)
sequences_indexer.add_token_sequences(token_sequences_train)
sequences_indexer.add_token_sequences(token_sequences_dev)
sequences_indexer.add_token_sequences(token_sequences_test)
sequences_indexer.add_tag_sequences(tag_sequences_train) # Surely, all necessarily tags must be into train data

# DatasetsBank provides storing the different dataset subsets (train/dev/test) and sampling batches from them
datasets_bank = DatasetsBank(sequences_indexer)
datasets_bank.add_train_sequences(token_sequences_train, tag_sequences_train)
datasets_bank.add_dev_sequences(token_sequences_dev, tag_sequences_dev)
datasets_bank.add_test_sequences(token_sequences_test, tag_sequences_test)

evaluator = Evaluator(sequences_indexer)

tagger = TaggerBiRNN(embeddings_tensor=sequences_indexer.get_embeddings_tensor(),
                     class_num=sequences_indexer.get_tags_num(),
                     rnn_hidden_size=rnn_hidden_size,
                     freeze_embeddings=freeze_embeddings,
                     dropout_ratio=dropout_ratio,
                     rnn_type='GRU',
                     gpu=gpu)

nll_loss = nn.NLLLoss(ignore_index=0) # "0" target values actually are zero-padded parts of sequences
optimizer = optim.SGD(list(tagger.parameters()), lr=lr, momentum=momentum)

iterations_num = int(datasets_bank.train_data_num / batch_size)
best_f1_dev = -1

for epoch in range(epoch_num):
    time_start = time.time()
    best_epoch_msg = ''
    for i in range(iterations_num):
        tagger.train()
        tagger.zero_grad()
        inputs_tensor_train_batch, targets_tensor_train_batch = datasets_bank.get_train_batch(batch_size)
        outputs_train_batch = tagger(inputs_tensor_train_batch)
        loss = nll_loss(outputs_train_batch, targets_tensor_train_batch)
        loss.backward()
        tagger.clip_gradients(clip_grad)
        optimizer.step()
        if i % 100 == 0:
            print('-- epoch = %d, i = %d/%d, loss = %1.4f' % (epoch, i, iterations_num, loss.item()))
    time_finish = time.time()
    f1_dev, precision_dev, recall_dev = evaluator.get_macro_scores(tagger, datasets_bank.inputs_tensor_dev,
                                                                   datasets_bank.targets_tensor_dev)
    if f1_dev > best_f1_dev:
        best_epoch_msg = '[BEST]'
        best_epoch = epoch
        best_f1_dev = f1_dev
        best_tagger = tagger
    print('\nEPOCH %d/%d, DEV: F1 = %1.3f, Precision = %1.3f, Recall = %1.3f,%s %d seconds.\n' % (epoch, epoch_num,
                                                                                                  f1_dev, precision_dev,
                                                                                                  recall_dev,
                                                                                                  best_epoch_msg,
                                                                                                  time.time() - time_start))
print('The end!')