"""Conservative line-level MWScript evidence scanner, not a compiler/interpreter."""
import copy
import re

# command: (kind, target argument index, expected argument count, count index)
COMMANDS={
    'additem':('inventory_add',0,2,1),'removeitem':('inventory_remove',0,2,1),
    'placeitem':('object_create',0,5,None),'placeitemcell':('object_create',0,6,None),
    'placeatpc':('object_create',0,4,1),'placeatme':('object_create',0,4,1),
    'addtolevitem':('list_add',1,3,None),'removefromlevitem':('list_remove',1,3,None),
    'addtolevcreature':('list_add',1,3,None),'removefromlevcreature':('list_remove',1,3,None),
    'journal':('journal_update',0,2,None),'setjournalindex':('journal_update',0,2,None),
    'startscript':('script_start',0,1,None),'stopscript':('script_stop',0,1,None),
}


def tokens(line):
    result=[];i=0
    while i<len(line):
        if line[i] in ' \t,':i+=1;continue
        if line[i]==';':break
        if line.startswith('->',i):result.append(('->',False));i+=2;continue
        if line[i]=='"':
            end=line.find('"',i+1)
            if end<0:raise ValueError('Unterminated quoted string')
            result.append((line[i+1:end],True));i=end+1;continue
        start=i
        while i<len(line) and line[i] not in ' \t,;"' and not line.startswith('->',i):i+=1
        result.append((line[start:i],False))
    return result


def candidate(token):
    if token is None:return None
    value,quoted=token
    if value and (quoted or re.fullmatch(r'[\w.:\\-]+',value)):
        return value.casefold()
    return None


def scan(source):
    events=[];warnings=[];stack=[];transfers=[];local_names=set()
    for line_number,line in enumerate(source.splitlines(),1):
        try:ts=tokens(line)
        except ValueError as exc:
            warnings.append((line_number,'tokenization',str(exc)));continue
        if not ts:continue
        head=ts[0][0].casefold() if not ts[0][1] else ''
        # Parentheses delimit control keywords even without intervening space.
        # Keep tokens and source lines unchanged for argument/context evidence.
        control=re.match(r'^(if|elseif|while)\(',head)
        if control:head=control.group(1)
        variable_positions=set()
        if head in ('short','long','float') and len(ts)>=2:
            local_names.add(ts[1][0].casefold());variable_positions.add(1)
        if head=='set' and len(ts)>=3 and not ts[2][1] and ts[2][0].casefold()=='to':
            variable_positions.add(1)
        if head in ('if','while'):
            stack.append({'kind':head,'branches':[{'line':line_number,'text':line}]});continue
        if head in ('elseif','else'):
            if not stack or stack[-1]['kind']!='if':warnings.append((line_number,'unmatched_branch',line))
            else:stack[-1]['branches'].append({'line':line_number,'text':line})
            continue
        if head in ('endif','endwhile'):
            if not stack or stack[-1]['kind']!=('if' if head=='endif' else 'while'):
                warnings.append((line_number,'unmatched_block_end',line))
            else:stack.pop()
            continue
        if head in ('return','break','continue'):
            transfers.append({'line':line_number,'text':line,'blocks':copy.deepcopy(stack)});continue
        receiver=None;command_index=0
        if len(ts)>=3 and ts[1]==('->',False):receiver=ts[0];command_index=2
        command=ts[command_index][0].casefold() if not ts[command_index][1] else ''
        if command not in COMMANDS:
            if any(not quoted and word.casefold() in COMMANDS
                   and word.casefold() not in local_names and i not in variable_positions
                   for i,(word,quoted) in enumerate(ts)):
                warnings.append((line_number,'unsupported_command_position',line))
            continue
        kind,target_index,expected,count_index=COMMANDS[command]
        args=ts[command_index+1:];notes=[]
        if len(args)!=expected:notes.append('argument_shape_unverified')
        target=candidate(args[target_index]) if len(args)>target_index else None
        if target is None:notes.append('target_unresolved')
        count=None
        if count_index is not None:
            if len(args)==expected and not args[count_index][1] and re.fullmatch(r'[+-]?\d+',args[count_index][0]):
                count=int(args[count_index][0])
            else:notes.append('count_expression_unresolved')
        receiver_key=candidate(receiver)
        recipient='player' if receiver_key=='player' else 'explicit_reference' if receiver else 'implicit_context'
        if command=='placeatpc':recipient='player_position'
        if command in ('placeitem','placeitemcell'):recipient='coordinate_destination'
        events.append({'line':line_number,'rawLine':line,'command':command,'kind':kind,
            'targetKey':target,'receiverKey':receiver_key,'recipientKind':recipient,
            'arguments':[{'text':t,'quoted':q} for t,q in args],'countLiteral':count,
            'context':{'blocks':copy.deepcopy(stack),'precedingControlTransfers':copy.deepcopy(transfers)},'notes':notes})
    if stack:warnings.append((len(source.splitlines()),'unclosed_blocks','Control blocks remain open'))
    for e in events:
        e['context']['sourceHasStructuralWarnings']=bool(warnings)
    return events,warnings
