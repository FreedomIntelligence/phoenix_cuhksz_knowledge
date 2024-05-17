import pandas as pd
import io,os,json,re
import random
import glob

base_data_path = os.environ['KG_BASE_PATH']

def is_isolated_word(full_text, data):

    word, start, end = data

    if not re.match(r'^[a-zA-Z]+$', word):
        return True

    # 检查前一个和后一个字符是否是英文字母
    before = start - 1
    after = end
    
    # 检查前后字符是否存在，如果存在且是英文字母，则返回False
    if before >= 0 and re.match(r'[a-zA-Z]', full_text[before]):
        return False
    if after < len(full_text) and re.match(r'[a-zA-Z]', full_text[after]):
        return False
    
    # 如果前后字符不是英文字母或不存在，则返回True
    return True

class DFADictChecker():

    def __init__(self):
        self.keyword_chains = {}
        self.delimit = '\x00'


    def add(self, keyword):
        if not isinstance(keyword, str):
            keyword = keyword.decode('utf-8')
        keyword = keyword.lower()
        chars = keyword.strip()
        if not chars:
            return
        level = self.keyword_chains
        for i in range(len(chars)):
            if chars[i] in level:
                level = level[chars[i]]
            else:
                if not isinstance(level, dict):
                    break
                for j in range(i, len(chars)):
                    level[chars[j]] = {}
                    last_level, last_char = level, chars[j]
                    level = level[chars[j]]
                last_level[last_char] = {self.delimit: 0}
                break
        if i == len(chars) - 1:
            level[self.delimit] = 0

    def parse(self, path):
        with open(path, 'rb') as f:
            for keyword in f:
                self.add(keyword.strip())

    def filter_with_pos(self, message, repl="*"):
        if not isinstance(message, str):
            message = message.decode('utf-8')
        message = message.lower()
        ret = []
        words = []
        start = 0
        while start < len(message):
            level = self.keyword_chains
            step_ins = 0
            for char in message[start:]:
                if char in level:
                    step_ins += 1
                    if self.delimit not in level[char]:
                        level = level[char]
                    else:
                        words.append([message[start:start + step_ins],start,start + step_ins])
                        ret.append(repl * step_ins)
                        level = level[char]
                        # 放开以后，就是只要先完成匹配的一个
                        # start += step_ins - 1
                        # break
                else:
                    ret.append(message[start])
                    break
            else:
                ret.append(message[start])
            start += 1

        return words

    def filter_no_overlap(self, message, repl="*"):
        raw_filter_words = self.filter_with_pos(message=message,repl=repl)
        raw_filter_words.sort(key=lambda x:len(x[0]),reverse=True)
        filter_results = []
        for item in raw_filter_words:
            flag = True
            for candi in filter_results:
                if candi[1] <= item[1] and candi[2] >= item[2]:
                    flag = False
                    break
            if flag:
                filter_results.append(item)
        return filter_results



class PhoenixKownledgeWrapper:

    def __init__(self) -> None:
        self.kg_ref_path = base_data_path
        self.key_refer = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'指代信息'))
        self.key_meta = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'元数据'))
        self.key_name = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'教职工人员'))
        self.key_build = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'建筑信息'))
        self.key_landmark = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'地标信息'))
        self.key_subject = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'专业信息'))
        self.key_faculty = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'院系信息'))
        # 内部维护
        self.key_secinfo = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'内部维护'))
        self.surprise = self.consist_group_taginfo(os.path.join(self.kg_ref_path,'彩蛋'))
        
        self.keywords_checker = DFADictChecker()
        self.tag_content_map = {}
        self.tag_type = {}
        self.parse()
        
    def consist_group_taginfo(self,dir_path):
        glob_paths = glob.glob(dir_path + '/*.md')
        reduce_datas = []

        for glb in glob_paths:
            contents = io.open(glb,'r').read()
            all_lines = contents.split('\n')
            tag = all_lines[0]
            info = '\n'.join(all_lines[1:])
            reduce_tag = tag.replace('keys:','')
            reduce_tag = reduce_tag.replace(',','|')[1:-1]
            reduce_tag = reduce_tag if '|' not in reduce_tag else '（' + reduce_tag + '）'
            reduce_datas.append({'tag':reduce_tag,'info':info,'path':glb})
        
        return pd.DataFrame(reduce_datas)

    def parse_sheet(self,sheet_data,except_set_checker):

        sheet_data = sheet_data.fillna('')
        for item_idx in range(len(sheet_data)):
            tag = str(sheet_data['tag'][item_idx]).lower()
            content = str(sheet_data['info'][item_idx]).replace('\\n','\n')
            if not tag or not content:
                continue
            try:
                if re.match('^（.*）$',tag) and '|' in tag:
                    all_tags = tag[1:-1].split('|')
                else:
                    all_tags = [tag]

                for i in range(len(all_tags)):
                    except_set_checker.add(all_tags[i])
                    
                    self.tag_content_map[all_tags[i]] = content
          

            except:
                except_set_checker.add(tag)
                self.tag_content_map[tag] = content.replace('\\n','\n')


    

    def parse(self):
        wait_list = [self.key_refer,self.key_meta,self.key_build,self.key_landmark,self.key_subject,self.key_faculty,self.surprise,self.key_name,self.key_secinfo]
        for key_item in wait_list:
            self.parse_sheet(key_item,self.keywords_checker)
        
        # self.parse_sheet(self.key_name,self.name_checker,True)  
    

    
    def get_tag_path(self,name):
            wait_list = [self.key_refer,self.key_meta,self.key_build,self.key_landmark,self.key_subject,self.key_faculty,self.surprise,self.key_name,self.key_secinfo]
            for type in wait_list:
                if name in type['tag'].values:
                    row_data = type[type['tag'] == name]
                    return row_data['path'].iloc[0]
                
            return None


    def rel_knowledge_concat(self,question,checker):
        name_list = checker.filter_no_overlap(question)
        name_desc_info = ''
        names = []

        tags_path = []

        for idx in range(len(name_list)):
            name_item = name_list[idx]
            is_isolate = is_isolated_word(question,name_item)
            name = name_item[0]
            if name in names or not is_isolate:
                continue
            names.append(name)
            desc = self.tag_content_map[name]
            name_desc_info += (f"{idx+1}.{name}:{desc}\n")

        for name in names:
            tag_path = self.get_tag_path(name)
            if tag_path:
                tags_path.append(tag_path)

     

        return name_desc_info,','.join(names), tags_path


    
    
    
    def wrap_question(self,question):
        content,keys,tags_path = self.rel_knowledge_concat(question,self.keywords_checker)
        
        if content:

            reduce_question = f'''#检索信息：<{keys}><{content}>#\n\n{question}'''
        else:
            reduce_question = question
        
        return reduce_question,tags_path


PhoenixKownledgeWrapper()