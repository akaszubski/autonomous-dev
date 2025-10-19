---
name: architecture-patterns
type: knowledge
description: Software architecture principles and design patterns (SOLID, DRY, design patterns, domain-driven design)
keywords: architecture, solid, dry, design pattern, separation of concerns, dependency injection, factory, strategy, observer
auto_activate: true
---

# Architecture Patterns Skill

Fundamental software architecture principles and design patterns.

## When This Activates
- Designing system architecture
- Refactoring code structure
- Applying design patterns
- Making architectural decisions
- Keywords: "architecture", "design pattern", "solid", "dry", "separation of concerns"

---

## SOLID Principles

### S - Single Responsibility Principle (SRP)
**Rule**: A class should have only one reason to change.

```python
# ❌ BAD: Multiple responsibilities
class UserManager:
    def create_user(self, data): ...
    def send_welcome_email(self, user): ...  # Email responsibility
    def log_user_creation(self, user): ...   # Logging responsibility
    def save_to_database(self, user): ...    # Persistence responsibility

# ✅ GOOD: Single responsibility per class
class UserCreator:
    def create_user(self, data): ...

class EmailService:
    def send_welcome_email(self, user): ...

class UserLogger:
    def log_creation(self, user): ...

class UserRepository:
    def save(self, user): ...
```

**Benefits**: Easier to test, maintain, and understand.

---

### O - Open/Closed Principle (OCP)
**Rule**: Open for extension, closed for modification.

```python
# ❌ BAD: Modifying existing code for new types
class ReportGenerator:
    def generate(self, report_type: str, data):
        if report_type == "pdf":
            return self._generate_pdf(data)
        elif report_type == "excel":
            return self._generate_excel(data)
        # Adding CSV requires modifying this class!

# ✅ GOOD: Extensible without modification
from abc import ABC, abstractmethod

class ReportGenerator(ABC):
    @abstractmethod
    def generate(self, data): ...

class PDFReportGenerator(ReportGenerator):
    def generate(self, data):
        return self._generate_pdf(data)

class ExcelReportGenerator(ReportGenerator):
    def generate(self, data):
        return self._generate_excel(data)

# Add CSV without modifying existing code
class CSVReportGenerator(ReportGenerator):
    def generate(self, data):
        return self._generate_csv(data)
```

**Benefits**: New features don't break existing code.

---

### L - Liskov Substitution Principle (LSP)
**Rule**: Subtypes must be substitutable for their base types.

```python
# ❌ BAD: Subtype changes expected behavior
class Rectangle:
    def set_width(self, width): self.width = width
    def set_height(self, height): self.height = height
    def area(self): return self.width * self.height

class Square(Rectangle):
    def set_width(self, width):
        self.width = width
        self.height = width  # Breaks LSP!

# ✅ GOOD: Use composition or separate hierarchies
class Shape(ABC):
    @abstractmethod
    def area(self): ...

class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height
    def area(self): return self.width * self.height

class Square(Shape):
    def __init__(self, side):
        self.side = side
    def area(self): return self.side ** 2
```

**Benefits**: Prevents unexpected behavior in polymorphic code.

---

### I - Interface Segregation Principle (ISP)
**Rule**: Clients shouldn't depend on interfaces they don't use.

```python
# ❌ BAD: Fat interface
class Worker(ABC):
    @abstractmethod
    def work(self): ...
    @abstractmethod
    def eat(self): ...
    @abstractmethod
    def sleep(self): ...

class Robot(Worker):
    def work(self): ...
    def eat(self): raise NotImplementedError  # Robots don't eat!
    def sleep(self): raise NotImplementedError  # Robots don't sleep!

# ✅ GOOD: Segregated interfaces
class Workable(ABC):
    @abstractmethod
    def work(self): ...

class Eatable(ABC):
    @abstractmethod
    def eat(self): ...

class Sleepable(ABC):
    @abstractmethod
    def sleep(self): ...

class Human(Workable, Eatable, Sleepable):
    def work(self): ...
    def eat(self): ...
    def sleep(self): ...

class Robot(Workable):
    def work(self): ...
```

**Benefits**: Smaller, focused interfaces are easier to implement.

---

### D - Dependency Inversion Principle (DIP)
**Rule**: Depend on abstractions, not concretions.

```python
# ❌ BAD: High-level module depends on low-level details
class EmailSender:
    def send(self, message): ...

class NotificationService:
    def __init__(self):
        self.email_sender = EmailSender()  # Tight coupling!

    def notify(self, message):
        self.email_sender.send(message)

# ✅ GOOD: Depend on abstraction
class MessageSender(ABC):
    @abstractmethod
    def send(self, message): ...

class EmailSender(MessageSender):
    def send(self, message): ...

class SMSSender(MessageSender):
    def send(self, message): ...

class NotificationService:
    def __init__(self, sender: MessageSender):
        self.sender = sender  # Depends on abstraction!

    def notify(self, message):
        self.sender.send(message)

# Usage
email_notifier = NotificationService(EmailSender())
sms_notifier = NotificationService(SMSSender())
```

**Benefits**: Easy to swap implementations, better testability.

---

## DRY (Don't Repeat Yourself)

**Rule**: Every piece of knowledge should have a single, authoritative representation.

```python
# ❌ BAD: Duplicated validation logic
def create_user(data):
    if not data.get('email'):
        raise ValueError("Email required")
    if '@' not in data['email']:
        raise ValueError("Invalid email")
    # ... create user

def update_user(user, data):
    if not data.get('email'):
        raise ValueError("Email required")
    if '@' not in data['email']:
        raise ValueError("Invalid email")
    # ... update user

# ✅ GOOD: Single source of truth
def validate_email(email: str) -> None:
    if not email:
        raise ValueError("Email required")
    if '@' not in email:
        raise ValueError("Invalid email")

def create_user(data):
    validate_email(data.get('email'))
    # ... create user

def update_user(user, data):
    validate_email(data.get('email'))
    # ... update user
```

**Benefits**: Changes in one place, consistent behavior.

---

## Separation of Concerns

**Rule**: Different concerns should be handled by different modules.

```python
# ❌ BAD: Mixed concerns
def process_order(order_data):
    # Validation
    if not order_data.get('items'):
        raise ValueError("No items")

    # Business logic
    total = sum(item['price'] * item['qty'] for item in order_data['items'])

    # Database
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders ...")

    # Email
    smtp = smtplib.SMTP('smtp.gmail.com')
    smtp.send_message(...)

    # Logging
    logging.info(f"Order processed: {total}")

# ✅ GOOD: Separated concerns
class OrderValidator:
    def validate(self, order_data): ...

class OrderCalculator:
    def calculate_total(self, items): ...

class OrderRepository:
    def save(self, order): ...

class OrderNotifier:
    def send_confirmation(self, order): ...

class OrderProcessor:
    def __init__(self, validator, calculator, repository, notifier):
        self.validator = validator
        self.calculator = calculator
        self.repository = repository
        self.notifier = notifier

    def process(self, order_data):
        self.validator.validate(order_data)
        total = self.calculator.calculate_total(order_data['items'])
        order = self.repository.save(order_data)
        self.notifier.send_confirmation(order)
```

**Benefits**: Testable, maintainable, reusable components.

---

## Common Design Patterns

### Factory Pattern
**When**: Need to create objects without specifying exact class.

```python
from abc import ABC, abstractmethod

class Model(ABC):
    @abstractmethod
    def train(self, data): ...

class MLXModel(Model):
    def train(self, data): ...

class PyTorchModel(Model):
    def train(self, data): ...

class ModelFactory:
    @staticmethod
    def create_model(backend: str) -> Model:
        if backend == "[framework]":
            return MLXModel()
        elif backend == "pytorch":
            return PyTorchModel()
        else:
            raise ValueError(f"Unknown backend: {backend}")

# Usage
model = ModelFactory.create_model("[framework]")
model.train(data)
```

**Benefits**: Decouples object creation from usage.

---

### Strategy Pattern
**When**: Need to switch between different algorithms at runtime.

```python
class TrainingStrategy(ABC):
    @abstractmethod
    def train(self, model, data): ...

class LoRAStrategy(TrainingStrategy):
    def train(self, model, data):
        # LoRA-specific training logic
        ...

class DPOStrategy(TrainingStrategy):
    def train(self, model, data):
        # DPO-specific training logic
        ...

class FullFinetuneStrategy(TrainingStrategy):
    def train(self, model, data):
        # Full finetune logic
        ...

class Trainer:
    def __init__(self, strategy: TrainingStrategy):
        self.strategy = strategy

    def set_strategy(self, strategy: TrainingStrategy):
        self.strategy = strategy

    def train(self, model, data):
        return self.strategy.train(model, data)

# Usage
trainer = Trainer(LoRAStrategy())
trainer.train(model, data)

# Switch strategy at runtime
trainer.set_strategy(DPOStrategy())
trainer.train(model, data)
```

**Benefits**: Easy to add new strategies without modifying existing code.

---

### Observer Pattern
**When**: Need to notify multiple objects of state changes.

```python
class Observer(ABC):
    @abstractmethod
    def update(self, event): ...

class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer: Observer):
        self._observers.append(observer)

    def detach(self, observer: Observer):
        self._observers.remove(observer)

    def notify(self, event):
        for observer in self._observers:
            observer.update(event)

class TrainingMetricsLogger(Observer):
    def update(self, event):
        if event['type'] == 'epoch_complete':
            logging.info(f"Epoch {event['epoch']}: Loss={event['loss']}")

class ProgressBar(Observer):
    def update(self, event):
        if event['type'] == 'batch_complete':
            self.progress.update(1)

# Usage
trainer = Subject()
trainer.attach(TrainingMetricsLogger())
trainer.attach(ProgressBar())

# During training
trainer.notify({'type': 'epoch_complete', 'epoch': 1, 'loss': 0.5})
```

**Benefits**: Loose coupling between subject and observers.

---

### Repository Pattern
**When**: Need to abstract data access logic.

```python
class ModelRepository(ABC):
    @abstractmethod
    def find_by_id(self, model_id: str): ...

    @abstractmethod
    def save(self, model): ...

    @abstractmethod
    def delete(self, model_id: str): ...

class MLXModelRepository(ModelRepository):
    def find_by_id(self, model_id: str):
        # Load from [FRAMEWORK] Hub
        ...

    def save(self, model):
        # Save to local storage
        ...

    def delete(self, model_id: str):
        # Delete from storage
        ...

class ModelService:
    def __init__(self, repository: ModelRepository):
        self.repository = repository

    def get_model(self, model_id: str):
        return self.repository.find_by_id(model_id)

# Usage
repo = MLXModelRepository()
service = ModelService(repo)
model = service.get_model("[model_repo]/Llama-3.2-3B-Instruct-4bit")
```

**Benefits**: Business logic doesn't depend on data storage details.

---

## Domain-Driven Design (DDD) Concepts

### Entities vs Value Objects

**Entity**: Has identity, mutable
```python
class User:
    def __init__(self, user_id: str, email: str):
        self.user_id = user_id  # Identity
        self.email = email

    def __eq__(self, other):
        return self.user_id == other.user_id  # Compare by ID
```

**Value Object**: No identity, immutable, compared by values
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self):
        if '@' not in self.value:
            raise ValueError(f"Invalid email: {self.value}")

# Two emails with same value are equal
email1 = Email("user@example.com")
email2 = Email("user@example.com")
assert email1 == email2  # True
```

---

### Aggregates
**Rule**: Group related entities under a single root.

```python
class Order:  # Aggregate Root
    def __init__(self, order_id: str):
        self.order_id = order_id
        self._items = []  # Aggregated entities

    def add_item(self, item):
        # Business logic in aggregate root
        if item.quantity <= 0:
            raise ValueError("Quantity must be positive")
        self._items.append(item)

    def total(self):
        return sum(item.price * item.quantity for item in self._items)

class OrderItem:  # Part of Order aggregate
    def __init__(self, product_id: str, quantity: int, price: float):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price

# Usage: Always access OrderItems through Order
order = Order("order-123")
order.add_item(OrderItem("prod-1", 2, 10.00))
```

**Benefits**: Maintains consistency boundaries.

---

## Layered Architecture

```
┌─────────────────────────┐
│   Presentation Layer    │  ← CLI, API, UI
├─────────────────────────┤
│   Application Layer     │  ← Use cases, orchestration
├─────────────────────────┤
│    Domain Layer         │  ← Business logic, entities
├─────────────────────────┤
│ Infrastructure Layer    │  ← Database, external APIs
└─────────────────────────┘
```

**Example**:
```python
# Domain Layer (core business logic)
class TrainingService:
    def train_model(self, model, dataset):
        # Business logic
        ...

# Application Layer (orchestration)
class TrainModelUseCase:
    def __init__(self, training_service, model_repo, dataset_repo):
        self.training_service = training_service
        self.model_repo = model_repo
        self.dataset_repo = dataset_repo

    def execute(self, model_id, dataset_id):
        model = self.model_repo.find_by_id(model_id)
        dataset = self.dataset_repo.find_by_id(dataset_id)
        return self.training_service.train_model(model, dataset)

# Presentation Layer (CLI)
def train_command(model_id, dataset_id):
    use_case = TrainModelUseCase(...)
    result = use_case.execute(model_id, dataset_id)
    print(f"Training complete: {result}")
```

**Benefits**: Clear separation, testable layers.

---

## Anti-Patterns to Avoid

### God Object
**Problem**: One class does everything

```python
# ❌ BAD
class [PROJECT_NAME]:
    def download_model(self): ...
    def prepare_data(self): ...
    def train_model(self): ...
    def evaluate_model(self): ...
    def deploy_model(self): ...
    # 50 more methods...
```

**Solution**: Split into focused classes (ModelDownloader, DataCurator, Trainer, etc.)

---

### Spaghetti Code
**Problem**: Tangled dependencies, no clear structure

**Solution**: Apply separation of concerns, define clear interfaces

---

### Premature Optimization
**Problem**: Optimizing before understanding requirements

**Solution**: Make it work, make it right, make it fast (in that order)

---

## When to Apply Patterns

**Good Reasons**:
- Solving a known, recurring problem
- Code is becoming hard to test or maintain
- Adding similar features repeatedly

**Bad Reasons**:
- "It's a best practice" (without understanding why)
- Anticipating future needs (YAGNI - You Aren't Gonna Need It)
- Making code "look professional"

---

## Integration with [PROJECT_NAME]

[PROJECT_NAME] uses these patterns:

1. **Factory Pattern**: `ModelFactory` for creating [FRAMEWORK]/PyTorch models
2. **Strategy Pattern**: `TrainingStrategy` for LoRA, DPO, Full FT
3. **Repository Pattern**: `ModelRepository`, `DatasetRepository`
4. **Separation of Concerns**: `backends/`, `core/`, `cli/` layers

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: python-standards, [framework]-patterns, testing-guide
