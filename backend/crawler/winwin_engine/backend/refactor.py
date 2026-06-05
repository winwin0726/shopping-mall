import sys

def modify_crawler_engine():
    path = r'd:\안티그래비티\winwin크롤러2\backend\crawler_engine.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    idx_start = content.find('        def _translate_one(seq_idx_tuple, use_critic=False, critic_prompt=""):')
    idx_worker = content.find('        def _worker_thread():')
    print(f'start={idx_start}, worker={idx_worker}')
    
    if idx_start > 0 and idx_worker > 0:
        translate_one_code = content[idx_start:idx_worker]
        lines = translate_one_code.split('\n')
        new_lines = []
        
        for i, line in enumerate(lines):
            if i == 0:
                new_lines.append('    def translate_single_item(self, idx, api_key, category, naver_fx, custom_prompt="", use_critic=False, critic_prompt="", seq=0, total=1):')
                continue
            if len(line) >= 4 and line.startswith('    '):
                new_lines.append(line[4:])
            else:
                new_lines.append(line)
                
        final_method = '\n'.join(new_lines)
        final_method = final_method.replace('seq, idx = seq_idx_tuple', '')
        final_method = final_method.replace('len(valid_indices)', 'total')
        
        idx_start_batch = content.find('    def start_batch_retranslate')
        new_content = content[:idx_start_batch] + final_method + '\n' + content[idx_start_batch:]
        
        idx_start_old = new_content.find('        def _translate_one(seq_idx_tuple, use_critic=False, critic_prompt=""):', idx_start_batch + len(final_method))
        idx_worker_old = new_content.find('        def _worker_thread():', idx_start_old)
        new_content = new_content[:idx_start_old] + new_content[idx_worker_old:]
        
        old_call = 'list(executor.map(lambda seq_idx: _translate_one(seq_idx, use_critic, critic_prompt), enumerate(valid_indices)))'
        new_call = 'list(executor.map(lambda seq_idx: self.translate_single_item(seq_idx[1], api_key, category, naver_fx, custom_prompt, use_critic, critic_prompt, seq=seq_idx[0], total=len(valid_indices)), enumerate(valid_indices)))'
        new_content = new_content.replace(old_call, new_call)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Refactoring completed successfully.')
    else:
        print('Could not find indices.')

if __name__ == '__main__':
    modify_crawler_engine()
