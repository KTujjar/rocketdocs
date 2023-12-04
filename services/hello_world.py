from schemas.hello_world import HelloWorldResponse


class HelloWorldService:
    def __init__(self):
        self.message = "Hello from RocketDocs!"

    def say_hello_world(self) -> HelloWorldResponse:
        # retrieve or create data
        data = {"message": self.message}

        # unpack into response model
        response = HelloWorldResponse(**data)

        # return the expected response
        return response


def get_hello_world_service() -> HelloWorldService:
    """
    This is used to initialize this class with any dependencies it needs,
    and inject it into the appropriate /routers router.
    """
    return HelloWorldService()


# The 'if' block bellow will only run if the file is run by itself,
# which makes it great for manually testing this file.
if __name__ == "__main__":
    service = get_hello_world_service()
    print("Here is the response: ", service.say_hello_world())
