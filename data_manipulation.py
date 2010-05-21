#!/usr/bin/env python2.6
# -*- coding: utf-8 -*-
import glob
import itertools
import os
import os.path
import re
import shutil
import sys

def createHmmDir(step):
    source_hmm_dir = 'hmm%02d' % (step - 1)
    target_hmm_dir = 'hmm%02d' % step
    if os.path.isdir(target_hmm_dir): shutil.rmtree(target_hmm_dir)
    os.mkdir(target_hmm_dir)
    
    return (source_hmm_dir, target_hmm_dir)
    
def createLogDirs():
    if not os.path.exists('log'): os.mkdir('log')
    if not os.path.exists('log/tasks'): os.mkdir('log/tasks')
    
def import_dictionaries(dicts):
    if os.path.isdir('dictionary'): shutil.rmtree('dictionary')
    os.mkdir('dictionary')
    dict = {}
    for location, prefix, word_suffix in dicts:
        if not os.path.exists(location + '/dict'):
            sys.exit("Not Found: " + location + '/dict')
            
        for line in open(location + '/dict'):
            word, transcription = line.split(None, 1)
            un_word = unescape(word.lower())
            un_word = un_word[0] + un_word[1:].replace('\\','')
            
            if not dict.has_key(un_word):
                dict[un_word] = []
                
            dict[un_word].append(
                [prefix + phone.lower() for phone in 
                     itertools.ifilterfalse(lambda x: (x == 'sil' or x == 'sp'),
                                  transcription.split())])
            
    new_dict = {}
    for word, transcriptions in dict.items():
        new_transcriptions = []
        for transcription in _unique_listelements(sorted(transcriptions, lambda x, y: len(x) - len(y))):
            new_transcriptions.append(transcription + ['sp'])
            new_transcriptions.append(transcription + ['sil'])
        new_dict[word+word_suffix] = new_transcriptions

    if new_dict.has_key('<s>'+word_suffix):
        del new_dict['<s>'+word_suffix]
    if new_dict.has_key('</s>'+word_suffix):
        del new_dict['</s>'+word_suffix]
    new_dict['<s>'] = [['sil']]
    new_dict['</s>'] = [['sil']]
    
    with open('dictionary/dict', 'w') as dictfile:
        for key in sorted(new_dict):
            for transcription in new_dict[key]:
                print >> dictfile, "%s %s" % (escape(key), ' '.join(transcription))

    new_dict = {}
    for word, transcriptions in dict.items():
        new_transcriptions = []
        for transcription in _unique_listelements(sorted(transcriptions, lambda x, y: len(x) - len(y))):
            new_transcriptions.append(transcription)
        new_dict[word+word_suffix] = new_transcriptions

    if new_dict.has_key('<s>'+word_suffix):
        del new_dict['<s>'+word_suffix]
    if new_dict.has_key('</s>'+word_suffix):
        del new_dict['</s>'+word_suffix]
    new_dict['<s>'] = [['sil']]
    new_dict['</s>'] = [['sil']]

    with open('dictionary/dict.hdecode', 'w') as dictfile:
        for key in sorted(new_dict):
            for transcription in new_dict[key]:
                print >> dictfile, "%s %s" % (escape(key), ' '.join(transcription))
    
def unescape(word):
    if re.match("^\\\\[^a-z0-9<]", word): return word[1:]
    else: return word

def escape(word):
    if re.match(u"^[^a-zäö0-9<]", word.decode('iso-8859-15')): return "\\" + word
    else: return word
    
def import_corpora(corpora):
    if os.path.isdir('corpora'): shutil.rmtree('corpora')
    os.mkdir('corpora')
    sets = ['train', 'eval', 'devel']
    
    locationmap = {}
    count = 0
    for location, prefix, word_suffix in corpora:
        if not os.path.exists(location + '/mfc'): sys.exit("Not Found: " + location + '/mfc')
        locationmap[location] = location + '/mfc'
        if os.path.islink(location + '/mfc'):
            count += 1
            os.symlink(os.path.join(os.path.dirname(location + '/mfc'), os.readlink(location + '/mfc')), 'corpora/mfc' + str(count))
            locationmap[location] = 'corpora/mfc' + str(count)
        
    for set in sets:
        with open('corpora/'+set+'.scp', 'w') as scpfile:
            for location, prefix, word_suffix in corpora:
                if not os.path.exists(location + '/'+set+'.scp'): sys.exit("Not Found: " + location + '/'+set+'.scp')
                for line in  open(location + '/'+set+'.scp'):
                    print >> scpfile, locationmap[location] + line[line.find('/'):].rstrip()
    
    with open('corpora/words.mlf', 'w') as mlffile:
        for location, prefix, word_suffix in corpora:
            if not os.path.exists(location + '/words.mlf'): sys.exit("Not Found: " + location + '/words.mlf')
            for line in open(location + '/words.mlf'):
                if line.startswith('#') or line.startswith('"') or line.startswith('.'):
                    if line.startswith('.'):
                        print >> mlffile, '</s>'
                    print >> mlffile, line.rstrip()
                    if line.startswith('"'):
                        print >> mlffile, '<s>'
                elif not line.startswith('<s>') and not line.startswith('</s>'):
                    print >> mlffile, prefix + line.rstrip() + word_suffix


def make_model_from_proto(hmm_dir, monophones):
    #Make a monophone model from the proto file generated by HCompV
    model_def = ""
    phone_def = ""
    in_model_def = True
    
    for line in open(hmm_dir + '/proto'):
        if line[0:2] == '~h': in_model_def = False
        if in_model_def: model_def += line
        else: phone_def += line
        
    #Write the macros file
    with open(hmm_dir + '/macros', 'w') as macros:
        print >> macros, model_def
        for line in open(hmm_dir + '/vFloors'):
            print >> macros, line
            
    #Write the hmmdefs file (replacing for each monophone, proto with the monophone)
    with open(hmm_dir + '/hmmdefs', 'w') as hmmdefs:
        for line in open(monophones):
            print >> hmmdefs, phone_def.replace('proto', line.rstrip())

def add_sp_to_phonelist(orig_phone_list, new_phone_list):
    with open(new_phone_list, 'w') as npl:
        for line in open(orig_phone_list):
            print >> npl, line.rstrip()
        print >> npl, 'sp'
    
def copy_sil_to_sp(source_hmm_dir, target_hmm_dir):
    in_sil = False
    in_state3 = False
    
    state = ""
    
    with open(target_hmm_dir + '/hmmdefs', 'w') as new_hmmdefs:
        for line in open(source_hmm_dir + '/hmmdefs'):
            print >> new_hmmdefs, line
            
            if line.startswith('~h'):
                if line.startswith('~h "sil"'): in_sil = True
                else: in_sil = False
            elif line.startswith('<STATE>'):
                if line.startswith('<STATE> 3'): in_state3 = True
                else: in_state3 = False
            elif in_sil and in_state3:
                state += line
    
        print >> new_hmmdefs, "~h \"sp\" <BEGINHMM> <NUMSTATES> 3"
        print >> new_hmmdefs, "<STATE> 2"
        print >> new_hmmdefs, state
        print >> new_hmmdefs, """<TRANSP> 3
         0.000000e+00 5.000000e-01 5.000000e-01
         0.000000e+00 5.000000e-01 5.000000e-01
         0.000000e+00 0.000000e+00 0.000000e+00
        <ENDHMM>"""
    
    shutil.copy(source_hmm_dir + '/macros', target_hmm_dir + '/macros')

def filter_scp_by_mlf(scp_orig, scp_new, mlf, report_list):
    scp = {}
    with open(scp_new, 'w') as scpfile:
        namere = re.compile('(?<=/)[a-zA-Z0-9]*(?=\.[^/]*$)')
        for line in open(scp_orig):
            m = namere.search(line)
            if m:
                scp[m.group(0)] = line.rstrip()
        
        for line in open(mlf):
            m = namere.search(line)
            if m:
                if scp.has_key(m.group(0)):
                    print >>  scpfile, scp[m.group(0)]
                    del scp[m.group(0)]
    with open(report_list, 'w') as reportfile:  
        for key in scp.keys():
            print >> reportfile, key
    
def remove_triphone_sil(file, unique = False):
    lines = []
    reg = re.compile("([a-z_]+\-sil)|(sil\+[a-z_]+)")
    
    for line in open(file):
        lines.append(reg.sub('sil', reg.sub('sil', line.rstrip())))
        #print lines[len(lines)-1]
        
    with open(file, 'w') as wfile:
        for line in lines:
            if not unique or (not line.rstrip() == 'sil' and not line.rstrip() == 'sil+sil'):
                print >> wfile, line
        if unique:
            print >> wfile, "sil"
        
def make_fulllist(phone_list, fulllist):
    phones = [] 
    for phone in open(phone_list):
        if phone.rstrip() != 'sp': phones.append(phone.rstrip())
    
    with open(fulllist, 'w') as flist:
        for phone1 in phones:
            for phone2 in phones:
                if phone2 != 'sil':
                    for phone3 in phones:
                        print >> flist, "%s-%s+%s" % (phone1, phone2, phone3)
        print >> flist, 'sp'
        print >> flist, 'sil'
                    
        
def make_tri_hed(triphones_list, phones_list, tri_hed):
    with open(tri_hed, 'w') as trihed:
        print >> trihed, "CL %s" % triphones_list
        for line in open(phones_list):
            print >> trihed, "TI T_%(phone)s {(*-%(phone)s+*,%(phone)s+*,*-%(phone)s).transP}" % {'phone': line.rstrip()}

def make_tree_hed(phone_rules_files, phones_list, tree_hed_file, tb, ro, statsfile, fulllist, tiedlist, trees):
    phones = [phone.rstrip() for phone in open(phones_list)]
    
    phone_rules = {}
    for location, prefix in phone_rules_files:
        for line in open(location):
            rule, phones = line.split(None, 1)
            if not phone_rules.has_key(rule):
                phone_rules[rule] = []
            phone_rules[rule].extend([prefix + phone.lower() for phone in phones.split()])
            
    for phone in open(phones_list):
        phone_rules[phone.rstrip()] = [phone.rstrip()]
    
    if phone_rules.has_key('sp'): del phone_rules['sp']
    if phone_rules.has_key('sil'): del phone_rules['sil']
    
    with open(tree_hed_file, 'w') as tree_hed:
        print >> tree_hed, "LS %s" % statsfile
        print >> tree_hed, "RO %.1f" % ro
        print >> tree_hed, "TR 0"
        
        for rule, phones in phone_rules.items():
            print >> tree_hed, 'QS "L_%s" {%s}' % (rule, ",".join([phone + '-*' for phone in phones]))
            print >> tree_hed, 'QS "R_%s" {%s}' % (rule, ",".join(['*+' + phone  for phone in phones]))
        
        print >> tree_hed, "TR 2"
        
        for state in range(2,5):
            for phone in open(phones_list):
                print >> tree_hed, 'TB %(tb).1f "%(phone)s_s%(state)d" {("%(phone)s","*-%(phone)s+*","%(phone)s+*","*-%(phone)s").state[%(state)d]}' % {'tb': tb, 'state': state, 'phone': phone.rstrip()}
        
        print >> tree_hed, "TR 1"
        
        print >> tree_hed, 'AU "%s"' % fulllist
        print >> tree_hed, 'CO "%s"' % tiedlist
        print >> tree_hed, 'ST "%s"' % trees

def _unique_listelements(iterable):
    "List unique elements, preserving order. Remember all elements ever seen."
    seen = set()
    seen_add = seen.add

    for element in iterable:
        k = ' '.join(element)
        if k not in seen:
            seen_add(k)
            yield element


#def create_scp_lists_speecon(speecon_dir):
#    hcopy_paths = []
#    create_dirs = set()
#
#    for waveset in ['train', 'devel', 'eval']:
#        waves = []
#
#        if not os.path.exists(speecon_dir + '/' + 'speecon_adult_' + waveset + '.recipe'):
#            sys.exit("Not Found: " + speecon_dir + '/' + 'speecon_adult_' + waveset + '.recipe')
#
#        for line in open(speecon_dir + '/' + 'speecon_adult_' + waveset + '.recipe'):
#            map = {}
#            for part in line.split():
#                (key, value) = part.split('=', 1)
#                map[key] = value
#            waves.append(map['audio'])
#
#        with open(waveset + '.scp', 'w') as real_scp:
#
#            for wave in waves:
#                pathcomps = wave.split('/')
#                pathcomps[len(pathcomps)-1] = pathcomps[len(pathcomps)-1].replace('FI0', 'mfc')
#                hcopy_paths.append( (wave , 'mfc/'+'/'.join(pathcomps[len(pathcomps)-3:]) ) )
#                create_dirs.add('mfc/'+'/'.join(pathcomps[len(pathcomps)-3:len(pathcomps)-1]))
#
#                print >> real_scp, "%s" % 'mfc/'+'/'.join(pathcomps[len(pathcomps)-3:])
#
#
#    for dir in create_dirs:
#        if not os.path.exists(dir): os.makedirs(dir)
#
#    with open('hcopy.scp', 'a') as hcopy_scp:
#
#        for path in hcopy_paths:
#            print >> hcopy_scp, "%s %s" % path
#
#def create_scp_lists_wsj(wsj_dir):
#    hcopy_paths = []
#    create_dirs = set()
#    source_dirs_map = {'train': [os.path.join(wsj_dir, 'wsj1', 'wsj1', dir) for dir in ['si_tr_s', 'si_tr_j', 'si_tr_jd', 'si_tr_l', 'si_dt_s6']],
#                   'devel': [os.path.join(wsj_dir, 'wsj1', 'wsj1', dir) for dir in ['si_dt_05']],
#                   'eval': [os.path.join(wsj_dir, 'wsj0', dir) for dir in ['si_tr_s', 'si_et_05']]}
#
#    for wave_set in ['train', 'devel', 'eval']:
#        source_dirs = source_dirs_map[waveset]
#
#        with open(wave_set + '.scp', 'w') as scp_file:
#            for source_dir in source_dirs:
#                if not os.path.isdir(source_dir):
#                    sys.exit("Location %s not found" % source_dir)
#
#                for file in glob.iglob(source_dir + '/*/*.wv1'):
#                    mfc_file = file.replace(source_dir, 'mfc').replace('wv1','mfc')
#                    hcopy_paths.append( (file, mfc_file) )
#                    create_dirs.add(os.path.dirname(mfc_file))
#                    print >> scp_file, mfc_file
#
#    for dir in create_dirs:
#        if not os.path.exists(dir): os.makedirs(dir)
#
#    with open('hcopy.scp', 'a') as hcopy_scp_file:
#        for path in hcopy_paths:
#            print >> hcopy_scp_file, "%s %s" % path

def create_scp_lists(waveforms, raw_to_wav_list, wav_to_mfc_list, exclude_list=None):
    excludes = []
    if exclude_list is not None:
        for line in open(exclude_list): excludes.append(line.rstrip())

    create_dirs = set()
    with open(raw_to_wav_list, 'w') as rtw_list:
        with open(wav_to_mfc_list, 'w') as wtm_list:
            for dset, files in waveforms.items():
                with open(dset + '.scp', 'w') as set_list:
                    for file in sorted(files):
                        dir, filename = os.path.split(file)
                        basen, ext = os.path.splitext(filename)
                        n_basen = basen.replace('_','')
                        if basen in excludes:
                            print basen + "excluded"
                            continue
                        wav_file = os.path.join('wav', dset, os.path.basename(dir), n_basen + '.wav')
                        mfc_file = os.path.join('mfc', dset, os.path.basename(dir), n_basen + '.mfc')
                        create_dirs.add(os.path.join('wav', dset, os.path.basename(dir)))
                        create_dirs.add(os.path.join('mfc', dset, os.path.basename(dir)))
                        print >> rtw_list, "%s %s" % (file, wav_file)
                        print >> wtm_list, "%s %s" % (wav_file, mfc_file)
                        print >> set_list, mfc_file
    
    for dir in create_dirs:
        if not os.path.exists(dir): os.makedirs(dir)

def create_wordtranscriptions_speecon(scp_files, speecon_dir, word_transcriptions):
    transcriptions = {}
    mappings = {}

    for line in open(os.path.join(speecon_dir, 'adult', 'TABLE', 'LEXICON.TBL')):
        parts = line.split('\t', 3)
        mappings[parts[0]] = parts[3].rstrip()


    for line in open(os.path.join(speecon_dir, 'adult', 'INDEX', 'CONTENT0.LST')):
        parts = line.split(None, 8)
        if len(parts) > 8:
            transcriptions[parts[1][0:8]] = parts[8].split('#')[0].split()

    with open(word_transcriptions, 'w') as transcriptions_file:
        print >> transcriptions_file, "#!MLF!#"
        for scp_file in scp_files:
            for line in open(scp_file):
                name = os.path.splitext(os.path.basename(line.rstrip()))[0]
                if not transcriptions.has_key(name):
                    sys.exit("No transcription found for %s" % name)

                print >> transcriptions_file, '"*/%s.mfc"' % name
                print >> transcriptions_file, '<s>'
                for word in transcriptions[name]:
                    word = word.replace('*', '')
                    if not word.startswith('[') and not word.startswith('Ö'):
                        if word.startswith('_') and mappings.has_key(word):
                            if mappings.has_key(mappings[word].lower()):
                                print >> transcriptions_file, mappings[mappings[word].lower()].lower() + '_'
                            elif mappings.has_key(mappings[word].upper()):
                                print >> transcriptions_file, mappings[mappings[word].upper()].lower() + '_'
                            else:
                                print >> transcriptions_file, word.lower().lstrip('_') + '_'
                        else:
                            print >> transcriptions_file, "%s_" % word.lower()
                print >> transcriptions_file, '</s>'
                print >> transcriptions_file, '.'

def update_exclude_list(exclude_list, excludes, scp_files, new_scp_files):
    with open(exclude_list, 'a') as exclude_file:
        for exclude in excludes:
            print >> exclude_file, exclude

    excludes = set()
    for exclude in open(exclude_list):
        excludes.add(exclude.rstrip())

    for old_scp, new_scp in itertools.izip(scp_files, new_scp_files):
        scp_lines = []
        for line in open(old_scp):
            line = line.rstrip()
            if os.path.splitext(os.path.basename(line))[0] not in excludes:
                scp_lines.append(line)

        with open(new_scp, 'w') as scp_file:
            for line in scp_lines:
                print >> scp_file, line
                
        
def prune_transcriptions(dict_file, orig_words_mlf, new_words_mlf):
    pruned_trans = []
    dict = {}
    for trans in open(dict_file):
        key,value = trans.split(None, 1)
        dict[key] = value


    reg_exp = re.compile('\"\*/([A-Za-z0-9]+)\.(mfc|lab)\"')
    with open(new_words_mlf, 'w') as mlf_out:
        print >> mlf_out, "#!MLF!#"
        utt_name = None
        utt_trans = []
        success = True

        for line in open(orig_words_mlf):
            line = line.rstrip()

            if line.startswith("#!MLF!#"):
                continue

            m = reg_exp.match(line)
            if m is not None:
                utt_name = m.group(1)
            elif line.lstrip().rstrip() == '.':
                utt_trans.append('.')
                if success and utt_name is not None:
                    print >> mlf_out, '"*/%s.lab"' % utt_name
                    for word in utt_trans:
                        print >> mlf_out, word
                else:
                    if utt_name is not None:
                        pruned_trans.append(utt_name)

                utt_name = None
                utt_trans = []
                success = True
            else:
                line = line[0] + line[1:].replace('\\','')
                if dict.has_key(line):
                    utt_trans.append(line)
                else:
                    success = False
                    print "%s is excluded because '%s' is not in the dictionary" % (utt_name, line)

    return pruned_trans


def create_wordtranscriptions_wsj(scp_files, wsj_dirs, word_transcriptions):
    transcriptions = {}

    delete_pattern = re.compile("(?<![\\\])[\(\)!:]")

    for file in itertools.chain(
            glob.iglob(os.path.join(wsj_dirs[0], 'transcrp', 'dots') + '/*/*/*.dot'),
            glob.iglob(wsj_dirs[0] + '/si_et_*/*/*.dot'),
            glob.iglob(os.path.join(wsj_dirs[1], 'trans', 'wsj1') + '/*/*/*.dot')):
        for line in open(file):
            parts = line.split()
            transcription = [re.sub(delete_pattern, '',  trans.lower().lstrip('(-~').rstrip(')~').replace('*', '')) for trans in parts[0:len(parts) - 1] if trans is not '.']
            file = parts[len(parts) -1][1:9].lower()
            transcriptions[file] = transcription

    with open(word_transcriptions, 'w') as transcriptions_file:
        print >> transcriptions_file, "#!MLF!#"
        for scp_file in scp_files:
            for line in open(scp_file):
                name = os.path.splitext(os.path.basename(line.rstrip()))[0]
                if not transcriptions.has_key(name):
                    sys.exit("No transcription found for %s" % name)

                print >> transcriptions_file, '"*/%s.mfc"' % name
                print >> transcriptions_file, '<s>'
                for word in transcriptions[name]:
                    if not word.startswith('[') and not word.startswith('<') and not word.endswith('-'):
                        if word.startswith('"'):
                           print >> transcriptions_file, "\%s" %  word 
                        elif len(word) > 0:
                            print >> transcriptions_file, word
                print >> transcriptions_file, '</s>'
                print >> transcriptions_file, '.'

def create_wordtranscriptions_dsp_eng(scp_files, dsp_eng_dir, word_transcriptions):
    transcriptions = {}
    for file in glob.iglob(dsp_eng_dir + '/*/*.txt'):
        id = os.path.splitext(os.path.basename(file))[0]
        trans = []
        for line in open(file):
            nline = line.replace('.', '')
            trans.extend(nline.split())
        transcriptions[id] = trans

    with open(word_transcriptions, 'w') as transcriptions_file:
        print >> transcriptions_file, "#!MLF!#"
        for scp_file in scp_files:
            for line in open(scp_file):
                name = os.path.splitext(os.path.basename(line.rstrip()))[0]
                n_name = name.replace('_', '')

                if not transcriptions.has_key(name):
                    sys.exit("No transcription found for %s" % name)

                print >> transcriptions_file, '"*/%s.mfc"' % n_name
                print >> transcriptions_file, '<s>'
                for word in transcriptions[name]:
                    if not word.startswith('[') and not word.startswith('<') and not word.endswith('-'):
                        if word.startswith('"'):
                           print >> transcriptions_file, "\%s" %  word
                        elif len(word) > 0:
                            print >> transcriptions_file, word
                print >> transcriptions_file, '</s>'
                print >> transcriptions_file, '.'

def create_wordtranscriptions_dsp_eng(scp_files, dsp_eng_dir, word_transcriptions):
    transcriptions = {}
    for file in glob.iglob(dsp_eng_dir + '/*/*.txt'):
        id = os.path.splitext(os.path.basename(file))[0].replace('_','')
        trans = []
        for line in open(file):
            nline = line.replace('.', '').replace(',', '')
            trans.extend(nline.split())
        transcriptions[id] = trans

    with open(word_transcriptions, 'w') as transcriptions_file:
        print >> transcriptions_file, "#!MLF!#"
        for scp_file in scp_files:
            for line in open(scp_file):
                name = os.path.splitext(os.path.basename(line.rstrip()))[0]
                n_name = name.replace('_', '')

                if not transcriptions.has_key(name):
                    sys.exit("No transcription found for %s" % name)

                print >> transcriptions_file, '"*/%s.mfc"' % n_name
                print >> transcriptions_file, '<s>'
                for word in transcriptions[name]:
                    if not word.startswith('[') and not word.startswith('<') and not word.endswith('-'):
                        if word.startswith('"'):
                           print >> transcriptions_file, "\%s" %  word
                        elif len(word) > 0:
                            print >> transcriptions_file, word
                print >> transcriptions_file, '</s>'
                print >> transcriptions_file, '.'


def create_wordtranscriptions_bl_eng(scp_files, bl_eng_dir, word_transcriptions):
    transcriptions = {}
    for line in open(os.path.join(bl_eng_dir, 'english_prompts.txt')):
        if len(line.rstrip()) > 0:
            tid, trans_str = line.split(None, 1)
            trans_str = trans_str.replace('.', '').replace(',', '')
            transcriptions[int(tid)] = trans_str.split()

    with open(word_transcriptions, 'w') as transcriptions_file:
        print >> transcriptions_file, "#!MLF!#"
        for scp_file in scp_files:
            for line in open(scp_file):
                name = os.path.splitext(os.path.basename(line.rstrip()))[0]
                id = int(name[-4:])


                if not transcriptions.has_key(id):
                    sys.exit("No transcription found for %s" % name)

                print >> transcriptions_file, '"*/%s.mfc"' % name
                print >> transcriptions_file, '<s>'
                for word in transcriptions[id]:
                    if not word.startswith('[') and not word.startswith('<') and not word.endswith('-'):
                        if word.startswith('"'):
                           print >> transcriptions_file, "\%s" %  word
                        elif len(word) > 0:
                            print >> transcriptions_file, word
                print >> transcriptions_file, '</s>'
                print >> transcriptions_file, '.'
                

def wsj_selection(wsj_dirs, files_set):
    wv1_files = []
    if files_set == 'si-84' or set == 'si-284':
        for line in open(os.path.join(wsj_dirs[0], 'doc', 'indices', 'train', 'tr_s_wv1.ndx')):
            if not line.startswith(';'):
                wv1_files.append(os.path.join(wsj_dirs[0], line.rstrip().split(':', 1)[1].split('/',1)[1]))
    if files_set == 'si-284':
        for file in glob.iglob(wsj_dirs[1] + '/si_tr_s/*/*.wv1'):
            wv1_files.append(file)
    if files_set == 'si_dt_05':
        for file in glob.iglob(wsj_dirs[1] + '/si_dt_05/*/*.wv1'):
            wv1_files.append(file)
    if files_set == 'si_et_05':
        for line in open(os.path.join(wsj_dirs[0], 'doc', 'indices', 'test', 'nvp', 'si_et_05.ndx')):
            if not line.startswith(';'):
                wv1_files.append(os.path.join(wsj_dirs[0], line.rstrip().split(':', 1)[1].split('/',1)[1]) + '.wv1')

#        for file in glob.iglob(wsj_dirs[0] + '/si_et_05/*/*.wv1'):
#            wv1_files.append(file)
    return list(set(wv1_files))

def speecon_fi_selection(speecon_dir, set):
    fi0_files = []
    if not os.path.exists(speecon_dir + '/' + 'speecon_adult_' + set + '.recipe'):
        sys.exit("Not Found: " + speecon_dir + '/' + 'speecon_adult_' + set + '.recipe')

    for line in open(speecon_dir + '/' + 'speecon_adult_' + set + '.recipe'):
        map = {}
        for part in line.split():
            (key, value) = part.split('=', 1)
            map[key] = value
        fi0_files.append(map['audio'].replace('/share/puhe/audio/speecon-fi', speecon_dir))
    return fi0_files

def dsp_eng_selection(dsp_eng_dir):
    wav_files = []
    wav_files = glob.glob(dsp_eng_dir + "/*/*.wav")
    return wav_files

def bl_eng_selection(bl_eng_dir):
    wav_files = []
    for file in glob.iglob(bl_eng_dir + "/wav_16khz/*/*.wav"):
        if int(os.path.splitext(os.path.basename(file))[0][-4:]) < 126:
            wav_files.append(file)
    return wav_files

    

def mlf_to_trn(mlf, trn, num_speaker_chars=3):
    reg_exp = re.compile('\".*/([A-Za-z0-9]+)\.(mfc|lab|rec)\"')

    utts_seen = set()

    with open(trn, 'w') as trn_file:
        utt_name = None
        trans = []
        for line in open(mlf):
            if line.startswith("#!MLF!#"):
                continue
            m = reg_exp.match(line)
            if m is not None:
                utt_name = m.group(1)
            elif line.lstrip().rstrip() == '.':
                if utt_name not in utts_seen:
                    trans.append("(%s_%s)" % (utt_name[:num_speaker_chars],utt_name[num_speaker_chars:]))
                    print >> trn_file, ' '.join(trans)
                    utts_seen.add(utt_name)
                trans = []
            elif not line.startswith('<'):
                trans.append(line.rstrip())
