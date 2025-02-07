# -*- coding: utf-8 -*-
"""
Created on Wed Sep 30 06:57:03 2020
主函数中的代码：可以将数据集转换成flair所需要的行列形式。

@author: tunan
"""
import json,os
from tqdm import tqdm
from bert4keras.snippets import sequence_padding, DataGenerator
from keras.utils.np_utils import to_categorical
from util import _init,set_value,get_value
from bert4keras.tokenizers import Tokenizer

def add_O(wordlabel,length):    
    '''输入:wordlabel(list(dict)),length(int),输入原句的长度和一条样本数据。
        输出:wordlabel(list(dict)),输出加入O实体后的一条样本。
        对一条样本加入O实体。
    '''
    d = []
    if len(wordlabel) == 0:
        d.append({'label_type':'O','start_pos':0,'end_pos':length})
    else:
        pre_x = wordlabel[0]
        prei1,prei2 = pre_x['start_pos'],pre_x['end_pos']
        if prei1 >0:
            d.append({'label_type':'O','start_pos':0,'end_pos':prei1})
        for x in wordlabel[1:]:
            i1,i2 = x['start_pos'],x['end_pos']
            if prei2<i1:
                d.append({'label_type':'O','start_pos':prei2,'end_pos':i1})
            prei1,prei2 = i1,i2
        if prei2<length:
            d.append({'label_type':'O','start_pos':prei2,'end_pos':length})
            
    wordlabel.extend(d)
    wordlabel = sorted(wordlabel,key = lambda x:x['start_pos'])  
    return wordlabel


def load_data(data):
    '''输入(list(str)):
        输出(list(str1,str2)):所有样本的标注数据。str1是句子实体，str2是实体类型。
        给定数据集数据，加载样本。
    '''
    def f(x):
        d = {'实验室检验':'检验','影像检查':'检查'}
        return d.get(x,x)
    
    D = []
    for line in tqdm(data):
        x = json.loads(line)  
        sentences = x['originalText']
        length = len(sentences)
        wordLabel = x['entities']
        wordlabel = sorted(wordLabel,key = lambda x:x['start_pos'])  
        wordlabel = add_O(wordlabel,length)  #添加不是实体的部分文本。
        
        d = []
        for x in wordlabel:
            i_beg,i_end = x['start_pos'],x['end_pos']
            word = sentences[i_beg:i_end]
            d.append([word,f(x['label_type'])])
        D.append(d)
    return D

#继承了自定义的DataGenerator
class data_generator(DataGenerator):
    """数据生成器
    初始化函数输入：data(list(str1,str2)),batch_size(int)。data是所有训练数据的集合，batch_size为样本大小。
    输出：对象.for_fit()方法返回一个迭代器。每次会返回一个batch的训练数据。
    """
    def __iter__(self, random=False):
        tokenizer,label2id,num_labels = get_value('tokenizer'),get_value('label2id'),get_value('num_labels')
        batch_token_ids, batch_segment_ids, batch_labels = [], [], []
        for is_end, item in self.sample(random):    #顺序取每条样本item，is_end为标记表示是否为最后一条记录。
            token_ids, labels = [tokenizer._token_start_id], [0] #cls的id和0
            for w, l in item:  #一条样本中的，每个word和label。
                w_token_ids = tokenizer.encode(w)[0][1:-1]  #对每段单词编码，得到所有字的id。
                if len(token_ids) + len(w_token_ids) < get_value('maxlen'): #如果已有的字小于最大长度，就加上当前id。
                    token_ids += w_token_ids
                    if l == 'O': #如果label为O，labels就直接增加对应长度的0。
                        labels += [0] * len(w_token_ids)
                    else:
                        B = label2id[l] * 2 + 1 #否则就对应到它的开头和中间部分，
                        I = label2id[l] * 2 + 2
                        labels += ([B] + [I] * (len(w_token_ids) - 1))
                else:
                    break
                
            #得到每个样本的字id和label id，长度等于句子长度。token_ids,labels
            #如果有一个实体正好在最大长度处卡断了，就去除整个实体。
            token_ids += [tokenizer._token_end_id]
            labels += [0]                        #输入和输出都加上结束符。label的开始符和结束符都为0。
            segment_ids = [0] * len(token_ids)   #分区id都为0.
            batch_token_ids.append(token_ids)    #将入到batch变量中。token_id，seg_id和label_id都加入batch变量中。
            batch_segment_ids.append(segment_ids)
            batch_labels.append(labels)
            if len(batch_token_ids) == self.batch_size or is_end:       #如果是最后一个单词，或者这个batch已经满了。
                batch_token_ids = sequence_padding(batch_token_ids)
                batch_segment_ids = sequence_padding(batch_segment_ids)
                batch_labels = sequence_padding(batch_labels)           #batch中的每个样本都padding到统一长度。
                batch_labels = to_categorical(batch_labels, num_classes=num_labels)
                yield [batch_token_ids, batch_segment_ids], batch_labels #返回一个batch的样本。
                batch_token_ids, batch_segment_ids, batch_labels = [], [], []
                
if __name__ == '__main__':
    data = []           #读取数据集
    data1_path =  r'.\datasets\yidu-s4k\subtask1_training_part1.txt'
    data2_path =  r'.\datasets\yidu-s4k\subtask1_training_part1.txt'
    test_data_path = r'.\datasets\yidu-s4k\subtask1_test_set_with_answer.json'
    with open(data1_path,'r',encoding='gbk') as f:
        data.extend(f.readlines())
    with open(data2_path,'r',encoding='gbk') as f:
        data.extend(f.readlines())
    test_data = []
    with open(test_data_path,'r',encoding='gbk') as f:
        test_data.extend(f.readlines())        

    X = load_data(data)     #分割数据集
    test_data = load_data(test_data) 
    
    _init()
    tokenizer = Tokenizer(get_value('dict_path'), do_lower_case=True)
    labels = ['疾病和诊断', '检查', '检验','手术','药物','解剖部位'] 
    id2label = dict(enumerate(labels))
    label2id = {j: i for i, j in id2label.items()}
    num_labels = len(labels) * 2 + 1
    
    set_value('labels',labels) 
    set_value('id2label',id2label)
    set_value('label2id',label2id)
    set_value('num_labels',num_labels)
    set_value('tokenizer',tokenizer)
    set_value('epochs',10)
    
    # tokenizer._tokenize('我们的祖国繁荣昌盛淼@loving!')
    def generate_one_sample(sample):
        '''说明：输入一条样本，生成对应行列格式的样本。
        输入sample(list(list))：一个样本，每个实体的文本值和对应的实体。
        输出d（list((str,str))):每个字（分词）和对应的实体标签label。
        '''
        d = []
        for i in range(len(sample)):
            entitle = sample[i][0]
            label = sample[i][1]
            e = tokenizer._tokenize(entitle)
            if label == 'O':
                l = len(e)*[label]
            else:
                l = ['B-'+label if i==0 else 'I-'+label for i in range(len(e))]
            d.extend(list(zip(e,l)))
        return d
    
    output = []
    for sample in X:
        d = generate_one_sample(sample)
        output.append('\n'.join([x[0]+' '+x[1] for x in d]))
    test_out = []
    for sample in test_data:
        d = generate_one_sample(sample)
        test_out.append('\n'.join([x[0]+' '+x[1] for x in d]))
        
    import random    
    random.seed(2020)
    random.shuffle(output)
    train_out = output[:int(len(X)*0.8)]
    train_out = '\n\n'.join(train_out)
    dev_out = output[int(len(X)*0.8):]
    dev_out = '\n\n'.join(dev_out)
    test_out = '\n\n'.join(test_out)
    with open(r'C:\Users\tunan\Desktop\bert_crf-model-in-ner\ccks\flair_project\dataset\train.txt','w',encoding='utf-8') as f:
        f.write(train_out)
    with open(r'C:\Users\tunan\Desktop\bert_crf-model-in-ner\ccks\flair_project\dataset\dev.txt','w',encoding='utf-8') as f:
        f.write(dev_out)
    with open(r'C:\Users\tunan\Desktop\bert_crf-model-in-ner\ccks\flair_project\dataset\test.txt','w',encoding='utf-8') as f:
        f.write(test_out)