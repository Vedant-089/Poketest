import os, time, math
from pathlib import Path
import torch, torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms
import timm
from tqdm.auto import tqdm

DATA_DIR    = Path("C:\images")         # <- change if needed
IMG_SIZE    = 224
INIT_BS     = 32                              # auto‑shrinks if OOM
EPOCHS      = 20
LR          = 3e-4
MODEL_NAME  = "convnext_tiny.fb_in22k"        # strong & fits Colab RAM
SEED        = 42
device      = "cuda" if torch.cuda.is_available() else "cpu"

torch.manual_seed(SEED)
torch.cuda.empty_cache()

# ------------------  Transforms  ------------------
train_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomAffine(15, translate=(0.05,0.05), scale=(0.9,1.1)),
    transforms.ColorJitter(0.2,0.2,0.2,0.1),
    transforms.ToTensor(),
    transforms.Normalize([0.5]*3, [0.5]*3),
])
val_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.5]*3, [0.5]*3),
])

# ------------------  Dataset & Loaders  ------------------
full_ds   = datasets.ImageFolder(DATA_DIR, transform=train_tf)
VAL_SPLIT = 0.10
val_len   = int(len(full_ds)*VAL_SPLIT)
train_len = len(full_ds)-val_len
train_ds, val_ds = random_split(full_ds, [train_len, val_len])
val_ds.dataset.transform = val_tf

def make_loaders(bs):
    return ( DataLoader(train_ds, bs, shuffle=True,  num_workers=0, pin_memory=True),
             DataLoader(val_ds,   bs, shuffle=False, num_workers=0, pin_memory=True) )

bs = INIT_BS
train_dl, val_dl = make_loaders(bs)
print(f"Dataset ready: {train_len} train, {val_len} val | {len(full_ds.classes)} classes")

# ------------------  Model, Opt, AMP  ------------------
num_classes = len(full_ds.classes)
model   = timm.create_model(MODEL_NAME, pretrained=True, num_classes=num_classes).to(device)
optimizer= torch.optim.AdamW(model.parameters(), lr=LR)
criterion= nn.CrossEntropyLoss()
scaler   = torch.cuda.amp.GradScaler()

# ------------------  Epoch Loops  ------------------
def epoch_pass(dataloader, train=True):
    model.train(train)
    correct = seen = loss_sum = 0
    pbar = tqdm(dataloader, leave=False)
    for x,y in pbar:
        x,y = x.to(device), y.to(device)
        if train: optimizer.zero_grad(set_to_none=True)
        with torch.cuda.amp.autocast():
            logits = model(x)
            loss   = criterion(logits, y)
        if train:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        preds   = logits.argmax(1)
        correct += torch.sum(preds.eq(y)).detach().cpu()
        seen    += y.size(0)
        loss_sum+= loss.detach().cpu()*y.size(0)
        pbar.set_postfix(acc=f"{(correct/seen)*100:.1f}%", bs=bs)
    return float(loss_sum/seen), float(correct/seen)

for epoch in range(1, EPOCHS+1):
    try:
        t0 = time.time()
        tr_loss, tr_acc = epoch_pass(train_dl, True)
        vl_loss, vl_acc = epoch_pass(val_dl,   False)
        print(f"E{epoch:02d}/{EPOCHS} "
              f"| train {tr_acc*100:5.1f}% {tr_loss:.3f} "
              f"| val {vl_acc*100:5.1f}% {vl_loss:.3f} "
              f"| {time.time()-t0:4.0f}s, bs={bs}")
        # Early‑stop if >90 % already
        if vl_acc >= 0.99:
            print("🎉 hit 99 %+ val accuracy – stopping early!")
            break
    except RuntimeError as e:
        if "out of memory" in str(e):
            torch.cuda.empty_cache()
            bs = bs // 2
            if bs < 4:
                raise RuntimeError("GPU too small even for batch_size=4.")
            print(f"⚠️  OOM – new batch_size={bs}")
            train_dl, val_dl = make_loaders(bs)
            continue
        else:
            raise e

# ------------------  Save  ------------------
torch.save(model.state_dict(), "model.pt")
print("✅ done – model saved as model.pt")

