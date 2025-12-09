# Architecture Patterns - Detailed Guide

## Common Architecture Patterns

### 1. Layered (N-Tier) Architecture

**Structure**:
```
┌─────────────────────────┐
│   Presentation Layer    │  (UI, Controllers)
├─────────────────────────┤
│    Business Logic       │  (Services, Domain)
├─────────────────────────┤
│    Data Access Layer    │  (Repositories, ORM)
├─────────────────────────┤
│       Database          │  (PostgreSQL, MySQL)
└─────────────────────────┘
```

**When to use**: Traditional web applications, CRUD-heavy systems

**Pros**:
- Simple to understand and implement
- Clear separation of concerns
- Easy to test each layer independently

**Cons**:
- Can become monolithic
- Changes ripple through layers
- Performance overhead from layer boundaries

**Example use case**: E-commerce website, internal business tools

---

### 2. Microservices Architecture

**Structure**:
```
┌────────────┐  ┌────────────┐  ┌────────────┐
│   User     │  │   Order    │  │  Payment   │
│  Service   │  │  Service   │  │  Service   │
└────────────┘  └────────────┘  └────────────┘
      │               │               │
      └───────────────┴───────────────┘
                  │
            ┌──────────────┐
            │ API Gateway  │
            └──────────────┘
```

**When to use**: Large teams, independent deployment needs, high scalability requirements

**Pros**:
- Independent deployment and scaling
- Team autonomy
- Technology diversity possible
- Fault isolation

**Cons**:
- Distributed system complexity
- Network latency
- Data consistency challenges
- Higher operational overhead

**Example use case**: Netflix, Amazon, large-scale SaaS platforms

---

### 3. Event-Driven Architecture

**Structure**:
```
┌────────────┐                   ┌────────────┐
│  Service A │───► Event Bus ───►│  Service B │
└────────────┘     (Kafka)       └────────────┘
                      │
                      ▼
                ┌────────────┐
                │  Service C │
                └────────────┘
```

**When to use**: Real-time systems, async workflows, event sourcing

**Pros**:
- Loose coupling between services
- Highly scalable
- Natural fit for real-time/streaming
- Easy to add new consumers

**Cons**:
- Debugging is harder (distributed traces)
- Event ordering challenges
- At-least-once/exactly-once semantics complexity

**Example use case**: Stock trading platforms, IoT systems, real-time analytics

---

### 4. Hexagonal Architecture (Ports & Adapters)

**Structure**:
```
         ┌──────────────────────┐
         │   Domain Logic       │
         │   (Business Rules)   │
         └──────────────────────┘
                  ▲    ▲
                  │    │
            ┌─────┘    └─────┐
            │                │
       ┌────▼────┐      ┌────▼────┐
       │  HTTP   │      │Database │
       │ Adapter │      │ Adapter │
       └─────────┘      └─────────┘
```

**When to use**: Domain-driven design, testability is critical

**Pros**:
- Business logic isolated from infrastructure
- Easy to test (mock adapters)
- Easy to swap implementations (e.g., swap database)

**Cons**:
- More initial setup
- Can be over-engineering for simple CRUD

**Example use case**: Banking systems, healthcare applications (domain-heavy)

---

### 5. Serverless Architecture

**Structure**:
```
API Gateway → Lambda → DynamoDB
            → Lambda → S3
            → Lambda → SQS
```

**When to use**: Variable/unpredictable load, event-driven tasks

**Pros**:
- No server management
- Pay-per-use pricing
- Auto-scaling
- Fast to deploy

**Cons**:
- Cold start latency
- Vendor lock-in
- Debugging is harder
- Limited execution time

**Example use case**: Image processing, webhooks, scheduled jobs

---

## Design Patterns (Gang of Four)

### Creational Patterns

#### Singleton

**Purpose**: Ensure only one instance exists

```python
class DatabaseConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.connection = create_connection()
        return cls._instance

# Usage
db1 = DatabaseConnection()  # Creates instance
db2 = DatabaseConnection()  # Returns same instance
assert db1 is db2  # True
```

**When to use**: Shared resources (DB connection, config, cache)

**Caution**: Can make testing difficult (global state)

---

#### Factory Pattern

**Purpose**: Create objects without specifying exact class

```python
class PaymentProcessorFactory:
    @staticmethod
    def create(payment_type: str):
        if payment_type == "credit_card":
            return CreditCardProcessor()
        elif payment_type == "paypal":
            return PayPalProcessor()
        elif payment_type == "crypto":
            return CryptoProcessor()
        raise ValueError(f"Unknown payment type: {payment_type}")

# Usage
processor = PaymentProcessorFactory.create("credit_card")
processor.process(amount=100)
```

**When to use**: Object creation logic is complex or conditional

---

### Structural Patterns

#### Adapter Pattern

**Purpose**: Make incompatible interfaces work together

```python
# Legacy system
class OldLogger:
    def log_message(self, msg):
        print(f"[OLD] {msg}")

# New interface
class Logger:
    def log(self, level, message):
        pass

# Adapter
class OldLoggerAdapter(Logger):
    def __init__(self, old_logger):
        self.old_logger = old_logger

    def log(self, level, message):
        self.old_logger.log_message(f"{level}: {message}")

# Usage
old = OldLogger()
adapter = OldLoggerAdapter(old)
adapter.log("INFO", "System started")  # Works with new interface!
```

**When to use**: Integrating legacy code, third-party libraries

---

#### Decorator Pattern

**Purpose**: Add behavior to objects dynamically

```python
# Base
class Coffee:
    def cost(self):
        return 2.00

# Decorators
class MilkDecorator:
    def __init__(self, coffee):
        self.coffee = coffee

    def cost(self):
        return self.coffee.cost() + 0.50

class SugarDecorator:
    def __init__(self, coffee):
        self.coffee = coffee

    def cost(self):
        return self.coffee.cost() + 0.25

# Usage
coffee = Coffee()
coffee = MilkDecorator(coffee)
coffee = SugarDecorator(coffee)
print(coffee.cost())  # 2.75
```

**When to use**: Add responsibilities without subclassing

---

### Behavioral Patterns

#### Strategy Pattern

**Purpose**: Select algorithm at runtime

```python
from abc import ABC, abstractmethod

class TrainingStrategy(ABC):
    @abstractmethod
    def train(self, model, data):
        pass

class LoRAStrategy(TrainingStrategy):
    def train(self, model, data):
        # LoRA-specific training
        pass

class DPOStrategy(TrainingStrategy):
    def train(self, model, data):
        # DPO-specific training
        pass

class Trainer:
    def __init__(self, strategy: TrainingStrategy):
        self.strategy = strategy

    def run(self, model, data):
        self.strategy.train(model, data)

# Usage
trainer = Trainer(LoRAStrategy())
trainer.run(model, data)

# Switch strategy
trainer.strategy = DPOStrategy()
trainer.run(model, data)
```

**When to use**: Multiple algorithms, select at runtime

---

#### Observer Pattern

**Purpose**: Notify dependents when state changes

```python
class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        self._observers.append(observer)

    def notify(self, event):
        for observer in self._observers:
            observer.update(event)

class Logger:
    def update(self, event):
        print(f"[LOG] {event}")

class EmailNotifier:
    def update(self, event):
        print(f"[EMAIL] Sending alert for: {event}")

# Usage
order_system = Subject()
order_system.attach(Logger())
order_system.attach(EmailNotifier())

order_system.notify("Order placed")  # Both observers notified
```

**When to use**: Event systems, publish-subscribe patterns

---

## System Design Principles

### SOLID Principles

#### S - Single Responsibility

**Rule**: A class should have ONE reason to change

```python
# ❌ BAD: Multiple responsibilities
class User:
    def save_to_database(self): ...
    def send_email(self): ...
    def generate_report(self): ...

# ✅ GOOD: Single responsibility
class User:
    pass

class UserRepository:
    def save(self, user): ...

class EmailService:
    def send_welcome_email(self, user): ...

class ReportGenerator:
    def generate_user_report(self, user): ...
```

---

#### O - Open/Closed

**Rule**: Open for extension, closed for modification

```python
# ❌ BAD: Must modify class to add new shapes
class AreaCalculator:
    def calculate(self, shapes):
        total = 0
        for shape in shapes:
            if shape.type == "circle":
                total += 3.14 * shape.radius ** 2
            elif shape.type == "square":
                total += shape.side ** 2
        return total

# ✅ GOOD: Extend via new classes
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        pass

class Circle(Shape):
    def area(self):
        return 3.14 * self.radius ** 2

class Square(Shape):
    def area(self):
        return self.side ** 2

class AreaCalculator:
    def calculate(self, shapes):
        return sum(shape.area() for shape in shapes)
```

---

#### L - Liskov Substitution

**Rule**: Subtypes must be substitutable for base types

```python
# ❌ BAD: Violates LSP
class Bird:
    def fly(self): pass

class Penguin(Bird):  # Penguins can't fly!
    def fly(self):
        raise NotImplementedError("Penguins can't fly")

# ✅ GOOD: Proper hierarchy
class Bird:
    pass

class FlyingBird(Bird):
    def fly(self): pass

class Sparrow(FlyingBird):
    def fly(self): ...

class Penguin(Bird):
    def swim(self): ...
```

---

#### I - Interface Segregation

**Rule**: Many specific interfaces > one general interface

```python
# ❌ BAD: Fat interface
class Worker:
    def work(self): pass
    def eat(self): pass

class Robot(Worker):  # Robots don't eat!
    def eat(self):
        raise NotImplementedError()

# ✅ GOOD: Segregated interfaces
class Workable:
    def work(self): pass

class Eatable:
    def eat(self): pass

class Human(Workable, Eatable):
    def work(self): ...
    def eat(self): ...

class Robot(Workable):
    def work(self): ...
```

---

#### D - Dependency Inversion

**Rule**: Depend on abstractions, not concretions

```python
# ❌ BAD: Depends on concrete class
class EmailService:
    pass

class NotificationManager:
    def __init__(self):
        self.email = EmailService()  # Hard dependency!

# ✅ GOOD: Depends on abstraction
from abc import ABC, abstractmethod

class Notifier(ABC):
    @abstractmethod
    def send(self, message): pass

class EmailNotifier(Notifier):
    def send(self, message): ...

class SMSNotifier(Notifier):
    def send(self, message): ...

class NotificationManager:
    def __init__(self, notifier: Notifier):
        self.notifier = notifier  # Depends on abstraction
```

---

### Other Key Principles

#### DRY (Don't Repeat Yourself)

**Rule**: Every piece of knowledge should have a single representation

```python
# ❌ BAD: Duplicated validation
def create_user(email):
    if "@" not in email:
        raise ValueError("Invalid email")
    ...

def update_user(email):
    if "@" not in email:  # Duplicated!
        raise ValueError("Invalid email")
    ...

# ✅ GOOD: Single source of truth
def validate_email(email):
    if "@" not in email:
        raise ValueError("Invalid email")

def create_user(email):
    validate_email(email)
    ...

def update_user(email):
    validate_email(email)
    ...
```

---

#### KISS (Keep It Simple, Stupid)

**Rule**: Simplest solution that works

```python
# ❌ BAD: Over-engineered
class AbstractFactoryBuilderSingletonProxy:
    def create_instance_with_dependency_injection():
        ...

# ✅ GOOD: Simple and clear
def create_user(name, email):
    return User(name=name, email=email)
```

---

#### YAGNI (You Aren't Gonna Need It)

**Rule**: Don't add functionality until needed

```python
# ❌ BAD: Adding features "just in case"
class User:
    def export_to_json(self): ...
    def export_to_xml(self): ...  # Do we need XML?
    def export_to_yaml(self): ...  # Do we need YAML?
    def export_to_csv(self): ...   # Do we need CSV?

# ✅ GOOD: Only what's needed now
class User:
    def export_to_json(self):  # Only JSON needed right now
        ...
```

---

## Tradeoff Analysis Framework
